# GRAVIX Android starter package

This package contains the edited Python app, Android build settings, Firebase security rules, and the server function used for authenticated training records. It is an MVP scaffold; it is not a finished commercial fitness platform.

## What the app does now

- Email/password sign-up and sign-in through Firebase Authentication. Passwords are sent to Firebase Auth and are not saved in the app database.
- Profile page with avatar/photo URL, height, weight, body-type preference, goal, level, XP, training records, streak, achievements, and a monthly activity calendar.
- A local catalogue of 43 common calisthenics skills and progressions, each with five stages, 20% steps, target-muscle labels, and an illustrative muscle-focus diagram. It is broad, not a claim to contain every variation ever practiced.
- A seven-day starter training week, session logging, skill-practice time, weekly mission records, and a global leaderboard updated by the server function.
- Manual calorie logging and an Android phone step-counter screen. Step sensor data is device-dependent; desktop builds cannot read phone sensors.
- Phone GPS permission and coordinate-based distance sorting for academy records from `/academy_directory`. Precise coordinates are stored in the user's private profile.
- Athlete listings for programs, 1:1 sessions, live links/Q&A, and skill-video links; comments on live/Q&A listings.
- Basic meal/macro estimates, skincare/grooming habits, external fitness-store/affiliate links, and a reminder that fires only while the app is open.

## What is still not a connected service

- AI video/form review, AI muscle visualization, and AI-counted push-up matches are not implemented. The muscle diagram is an illustration. Video links are saved as pending review.
- The 1v1 result form is self-reported. It does not verify a remote opponent or award ranking points.
- Live items are links plus comments; there is no streaming service, chat moderation, or creator payout.
- Paid programs, 1:1 bookings, meal plans, academy referrals/commissions, and marketplace purchases are requests only. No payment provider, payout, or payment webhook is configured.
- The store is a list of seller/affiliate links; checkout happens on the external seller's site.
- Academy search sorts academy records already loaded into Firebase. It does not discover academies from a maps/places provider.
- Reminders are checked while the app runs. Reliable background notifications need a push/notification service and platform setup.
- Meals and calorie/macronutrient figures are broad examples, not a food database or personalized medical plan.

## Firebase setup

1. In Firebase Authentication, enable Email/Password sign-in.
2. Confirm the Realtime Database URL in `gravix_app.py` points to the intended Firebase project.
3. Add the Firebase Web API key to the GitHub repository secret named `GRAVIX_FIREBASE_API_KEY`. It is a public client identifier embedded in the APK, not a server credential; restrict it in Google Cloud.
4. Deploy the database rules and the callable function from this directory with the Firebase CLI: `firebase deploy --only database,functions`.
5. Populate `/academy_directory` with public academy records. Do not put private referral or payment records in that public directory.
6. Add listing records only through the app or a trusted admin workflow. The transaction area is writable only by trusted server code.

The function awards limited XP/rank points from supported activity types, applies daily submission caps, stores daily tracker updates idempotently, and writes leaderboard totals. Client-supplied `rank_points` values are ignored. Firebase Admin credentials are provided by Firebase during function deployment; never add a service-account JSON file to this repository.

## Build a debug APK with GitHub Actions

1. Copy the contents of this package to the root of your own GitHub repository, including the hidden `.github` folder.
2. Add the repository secret `GRAVIX_FIREBASE_API_KEY`. If your Firebase Functions URL is different, set the repository variable `GRAVIX_FUNCTIONS_URL`.
3. Push to `main`/`master`, or open **Actions → Build GRAVIX Android APK → Run workflow**.
4. When the job finishes, download the `gravix-debug-apk` artifact from that run and extract the APK.

The output is a debug-signed APK for installation/testing. It is not a Play Store release. Publishing requires a protected signing key and a release build. Buildozer's Android packaging runs on Linux/macOS or Windows through WSL; the current machine has no WSL/Buildozer toolchain, so no APK was compiled here.

## Security and privacy limits

No app can be guaranteed impossible to hack. This package uses Firebase Authentication, UID-scoped database rules, private profile data, and server-owned XP/leaderboard writes as a stronger baseline. It does not include Firebase App Check, account verification flows, anti-abuse monitoring, a payment provider, or a security audit. Apply the rules before using real accounts and data. A compromised phone or a user falsifying self-reported activity remains possible; AI/video verification and paid transactions need trusted backend services.

The app stores height, weight, body-type preference, goals, and optional precise location. Keep those fields private, request only permissions users need, and publish a privacy policy before distributing the app.
