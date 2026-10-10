const { initializeApp } = require("firebase-admin/app");
const { getDatabase } = require("firebase-admin/database");
const { onCall, HttpsError } = require("firebase-functions/v2/https");

initializeApp();
const db = getDatabase();

const CAPS = {
  workout: 4,
  program_session: 3,
  skill_practice: 12,
  pushup_match: 10,
};

function boundedInteger(value, name, max) {
  if (value === undefined || value === null || value === "") return 0;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 0 || parsed > max) {
    throw new HttpsError("invalid-argument", `Invalid ${name}.`);
  }
  return parsed;
}

function localDate(value) {
  const date = typeof value === "string" ? value : "";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    throw new HttpsError("invalid-argument", "Invalid activity date.");
  }
  const millis = Date.parse(`${date}T12:00:00Z`);
  if (!Number.isFinite(millis)) {
    throw new HttpsError("invalid-argument", "Invalid activity date.");
  }
  const today = new Date();
  const utcToday = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  const submitted = Date.UTC(new Date(millis).getUTCFullYear(),
    new Date(millis).getUTCMonth(), new Date(millis).getUTCDate());
  if (Math.abs(submitted - utcToday) > 86400000) {
    throw new HttpsError("invalid-argument", "Activity date is outside the current day window.");
  }
  return date;
}

function scoreFor(kind, details) {
  if (kind === "workout" && details.workout_minutes > 0) return 25;
  if (kind === "program_session" && details.workout_minutes > 0) return 20;
  if (kind === "skill_practice" && details.skill_minutes > 0) return 10;
  return 0;
}

function dayDifference(from, to) {
  return Math.round((Date.parse(`${to}T12:00:00Z`) -
    Date.parse(`${from}T12:00:00Z`)) / 86400000);
}

exports.recordActivity = onCall({ region: "asia-southeast1" }, async (request) => {
  const uid = request.auth && request.auth.uid;
  if (!uid) throw new HttpsError("unauthenticated", "Sign in to record training.");

  const input = request.data || {};
  const kind = String(input.kind || "");
  if (!Object.hasOwn(CAPS, kind) && kind !== "daily_tracker") {
    throw new HttpsError("invalid-argument", "Unsupported activity type.");
  }
  const raw = input.details && typeof input.details === "object" ? input.details : {};
  const date = localDate(raw.local_date);
  const details = {
    workout_minutes: boundedInteger(raw.workout_minutes, "workout minutes", 600),
    skill_minutes: boundedInteger(raw.skill_minutes, "skill minutes", 600),
    steps: boundedInteger(raw.steps, "steps", 100000),
    calories: boundedInteger(raw.calories, "calories", 10000),
    reps: boundedInteger(raw.reps, "reps", 10000),
    skill_id: typeof raw.skill_id === "string" ? raw.skill_id.slice(0, 64) : "",
    program_day: typeof raw.program_day === "string" ? raw.program_day.slice(0, 64) : "",
  };
  if (kind === "skill_practice" && !details.skill_id) {
    throw new HttpsError("invalid-argument", "Choose a skill to record.");
  }
  if (["workout", "program_session"].includes(kind) && details.workout_minutes < 1) {
    throw new HttpsError("invalid-argument", "Record at least one training minute.");
  }
  if (kind === "skill_practice" && details.skill_minutes < 1) {
    throw new HttpsError("invalid-argument", "Record at least one skill-practice minute.");
  }
  if (kind === "daily_tracker" && details.steps + details.calories +
      details.skill_minutes < 1) {
    throw new HttpsError("invalid-argument", "Add a non-zero tracker value.");
  }
  if (kind === "pushup_match" && details.reps < 1) {
    throw new HttpsError("invalid-argument", "Record at least one push-up.");
  }

  const userRef = db.ref(`users/${uid}`);
  const randomRecordKey = userRef.child("activity").push().key;
  const dailyKey = `daily_${date}`;
  const stamp = new Date().toISOString();
  let savedStats = null;
  const result = await userRef.transaction((current) => {
    const root = current && typeof current === "object" ? current : {};
    const guardrails = { ...(root.guardrails || {}) };
    const dailyGuard = { ...(guardrails[date] || {}) };
    const cap = CAPS[kind];
    if (cap && Number(dailyGuard[kind] || 0) >= cap) return;
    if (cap) dailyGuard[kind] = Number(dailyGuard[kind] || 0) + 1;
    guardrails[date] = dailyGuard;

    const stats = { ...(root.stats || {}) };
    const activity = { ...(root.activity || {}) };
    const previous = kind === "daily_tracker" && activity[dailyKey]
      ? activity[dailyKey] : {};
    const savedSteps = kind === "daily_tracker"
      ? Math.max(Number(previous.steps || 0), details.steps) : details.steps;
    const savedCalories = kind === "daily_tracker"
      ? Math.max(Number(previous.calories || 0), details.calories) : details.calories;
    const savedSkillMinutes = kind === "daily_tracker"
      ? Math.max(Number(previous.skill_minutes || 0), details.skill_minutes)
      : details.skill_minutes;
    const deltaSteps = savedSteps - Number(previous.steps || 0);
    const deltaCalories = savedCalories - Number(previous.calories || 0);
    const deltaSkillMinutes = savedSkillMinutes - Number(previous.skill_minutes || 0);
    const points = scoreFor(kind, details);
    const workoutMinutes = details.workout_minutes;
    const activityRecord = {
      date,
      timestamp: stamp,
      type: kind,
      workout_minutes: workoutMinutes,
      skill_minutes: savedSkillMinutes,
      steps: savedSteps,
      calories: savedCalories,
      reps: details.reps,
      skill_id: details.skill_id,
      program_day: details.program_day,
      rank_points_awarded: points,
    };
    activity[kind === "daily_tracker" ? dailyKey : randomRecordKey] = activityRecord;

    const xpTotal = Number(stats.xp_total || stats.xp || 0) + points;
    let remainder = xpTotal;
    let level = 0;
    while (remainder >= 100 + level * 50) {
      remainder -= 100 + level * 50;
      level += 1;
    }
    const completedWorkouts = Number(stats.completed_workouts || 0) +
      ((["workout", "program_session"].includes(kind) && workoutMinutes > 0) ? 1 : 0);
    const nextStats = {
      ...stats,
      level,
      xp: remainder,
      xp_total: xpTotal,
      rank_points: Number(stats.rank_points || 0) + points,
      workout_minutes: Number(stats.workout_minutes || 0) + workoutMinutes,
      skill_minutes: Number(stats.skill_minutes || 0) +
        (kind === "daily_tracker" ? deltaSkillMinutes : details.skill_minutes),
      steps: Number(stats.steps || 0) + deltaSteps,
      calories: Number(stats.calories || 0) + deltaCalories,
      completed_workouts: completedWorkouts,
      achievements: Number(stats.achievements || 0),
    };

    const dates = new Set(Object.values(activity)
      .filter((item) => item && item.date).map((item) => item.date));
    let streak = 0;
    let cursor = date;
    while (dates.has(cursor)) {
      streak += 1;
      const next = new Date(`${cursor}T12:00:00Z`);
      next.setUTCDate(next.getUTCDate() - 1);
      cursor = next.toISOString().slice(0, 10);
    }
    nextStats.streak = Math.max(Number(stats.streak || 0), streak);

    const achievements = { ...(root.achievements || {}) };
    const candidates = [
      ["first_session", completedWorkouts >= 1, "First training session"],
      ["ten_sessions", completedWorkouts >= 10, "Ten training sessions"],
      ["ten_skill_practices", Object.values(activity).filter(
        (item) => item && item.type === "skill_practice").length >= 10,
       "Ten skill practices"],
      ["six_hundred_minutes", Number(nextStats.workout_minutes) >= 600,
       "600 minutes of training"],
    ];
    for (const [id, unlocked, title] of candidates) {
      if (unlocked && !achievements[id]) {
        achievements[id] = { title, unlocked_at: stamp };
      }
    }
    nextStats.achievements = Object.keys(achievements).length;
    root.stats = nextStats;
    root.activity = activity;
    root.achievements = achievements;
    root.guardrails = guardrails;
    savedStats = nextStats;
    return root;
  }, undefined, false);

  if (!result.committed) {
    throw new HttpsError("resource-exhausted", "Daily recording limit reached for this activity.");
  }
  const profile = result.snapshot.child("profile").val() || {};
  const stats = result.snapshot.child("stats").val() || savedStats;
  await db.ref(`leaderboard/${uid}`).set({
    display_name: String(profile.display_name || "GRAVIX athlete").slice(0, 50),
    level: Number(stats.level || 0),
    rank_points: Number(stats.rank_points || 0),
    updated_at: stamp,
  });
  return {
    saved: true,
    level: Number(stats.level || 0),
    xp: Number(stats.xp || 0),
    rank_points: Number(stats.rank_points || 0),
  };
});
