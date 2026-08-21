# GRAVIX Android Build

This project is configured to build the Kivy app as an Android APK using GitHub Actions.

## Files
- `main.py` — app entry point
- `Buildozer.spec` — Android build configuration
- `calisthenics.db` — included with the app package (the current Python code uses Firebase for live data)
- `.github/workflows/build-apk.yml` — automated GitHub build

## Build
1. Create a GitHub repository.
2. Upload all files/folders from this project.
3. Push to the `main` branch, or open GitHub Actions and run **Build GRAVIX Android APK** manually.
4. When the workflow finishes, open the workflow run and download the **GRAVIX-APK** artifact.
5. Extract the artifact to get the `.apk`.

Firebase is left as the live backend configured in `main.py`.
