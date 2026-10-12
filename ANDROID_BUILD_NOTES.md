# GRAVIX Android build and retest

The app source now includes a 24-hour step session and a separate Android
foreground service. The service is included only when it is declared in the
project's Buildozer configuration. No Buildozer project file was supplied with
the app source, so merge these entries into the existing `buildozer.spec`:

```ini
icon.filename = %(source.dir)s/gravix_launcher_icon.png
services = Steptracker:gravix_step_service.py:foreground:sticky:foregroundServiceType=health
android.permissions = INTERNET, ACTIVITY_RECOGNITION, FOREGROUND_SERVICE, FOREGROUND_SERVICE_HEALTH, POST_NOTIFICATIONS
```

If the existing `android.permissions` line contains other permissions, keep
them and append the four shown above. Keep `gravix_app.py` as the app entry
point expected by your project (often renamed to `main.py`), and place
`gravix_step_service.py` and `gravix_launcher_icon.png` in `source.dir`.

## Rebuild and check on Android

1. Rebuild the APK after adding the service and permissions. Reinstall it so
   Android receives the updated foreground-service manifest and icon.
2. Sign in, open **Step Quest**, start the 24-hour quest, and grant
   **Physical activity** permission. Allow notifications so the ongoing
   tracking notification is visible.
3. Close GRAVIX from the recent-apps view, walk for several minutes, reopen,
   and confirm the count advanced. Then save the current step total and check
   the activity record.
4. Confirm the launcher icon appears after installation and that **Log out**
   stops the step service. The active quest ends at 24 hours.

The phone must have a hardware step-counter sensor. Android may stop a service
after a force-stop, and a reboot resets the hardware's since-boot step count;
open GRAVIX again after either event to resume an unexpired saved quest.
