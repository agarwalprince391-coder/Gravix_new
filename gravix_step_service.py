"""Android foreground service for the GRAVIX 24-hour step quest.

Include this script as a python-for-android service in the Android package.
The foreground app passes only its local database path and the signed-in
user's local step-record key; Firebase credentials are never sent to this
service.
"""
import json
import os
import sqlite3
import time

from jnius import autoclass, PythonJavaClass, java_method


class _ServiceStepListener(PythonJavaClass):
    __javainterfaces__ = ["android/hardware/SensorEventListener"]

    def __init__(self, db_path, user_id):
        super().__init__()
        self.db_path = db_path
        self.user_id = user_id

    @java_method("(Landroid/hardware/SensorEvent;)V")
    def onSensorChanged(self, event):
        try:
            _apply_sensor_total(self.db_path, self.user_id,
                                float(event.values[0]))
        except Exception:
            pass

    @java_method("(Landroid/hardware/Sensor;I)V")
    def onAccuracyChanged(self, sensor, accuracy):
        pass


def _connect(path):
    db = sqlite3.connect(path, timeout=10)
    db.execute("PRAGMA busy_timeout=10000")
    return db


def _read_session(db_path, user_id):
    try:
        with _connect(db_path) as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT * FROM step_sessions WHERE user_id=?",
                (user_id,)).fetchone()
            return dict(row) if row else None
    except (sqlite3.Error, OSError):
        return None


def _apply_sensor_total(db_path, user_id, total):
    """Atomically accumulate one hardware counter reading in the shared DB."""
    with _connect(db_path) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("""SELECT expires_at, steps, latest, tracking_enabled
            FROM step_sessions WHERE user_id=?""", (user_id,)).fetchone()
        if not row:
            db.rollback()
            return
        expires_at, steps, previous_total, enabled = row
        if not enabled or time.time() >= float(expires_at):
            db.rollback()
            return
        steps = int(steps)
        if previous_total is not None and total >= float(previous_total):
            steps += int(total - float(previous_total))
        # The phone rebooted and reset its since-boot sensor count. Keep the
        # accumulated quest total and use this reading as the next baseline.
        db.execute("UPDATE step_sessions SET steps=?, latest=? WHERE user_id=?",
                   (steps, total, user_id))
        db.commit()


def _stop_foreground_service(service, manager=None, listener=None):
    try:
        if manager is not None and listener is not None:
            manager.unregisterListener(listener)
    except Exception:
        pass
    try:
        service.setAutoRestartService(False)
    except Exception:
        pass
    try:
        service.stopSelf()
    except Exception:
        pass


def main():
    service = autoclass("org.kivy.android.PythonService").mService
    if service is None:
        return
    try:
        service.setAutoRestartService(True)
    except Exception:
        pass

    try:
        config = json.loads(os.environ.get("PYTHON_SERVICE_ARGUMENT", "{}"))
        db_path = config["db_path"]
        user_id = config["user_id"]
        if not os.path.isfile(db_path):
            _stop_foreground_service(service)
            return

        sensor_api = autoclass("android.hardware.Sensor")
        manager_api = autoclass("android.hardware.SensorManager")
        context_api = autoclass("android.content.Context")
        manager = service.getSystemService(context_api.SENSOR_SERVICE)
        sensor = manager.getDefaultSensor(sensor_api.TYPE_STEP_COUNTER)
        if sensor is None:
            _stop_foreground_service(service)
            return

        listener = _ServiceStepListener(db_path, user_id)
        registered = manager.registerListener(
            listener, sensor, manager_api.SENSOR_DELAY_NORMAL)
        if not registered:
            _stop_foreground_service(service, manager, listener)
            return

        while True:
            time.sleep(3)
            session = _read_session(db_path, user_id)
            if (not session or not session.get("tracking_enabled") or
                    time.time() >= float(session.get("expires_at", 0))):
                _stop_foreground_service(service, manager, listener)
                return
    except Exception:
        # Sticky service configuration lets Android restart after transient
        # process failure. The foreground app reports when the service cannot
        # be started or the device lacks a step-counter sensor.
        try:
            service.setAutoRestartService(True)
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
