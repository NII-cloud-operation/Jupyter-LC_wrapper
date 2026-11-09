# Making a new release of lc_wrapper

Use `YYYY.M.N` versions and `vYYYY.M.N` tags.
Start `N` at `0` each month and increment it for subsequent releases.

1. Update the version in `package.json`.
2. Commit the changes and push a matching version tag, such as `v<version>`.
3. The Release workflow builds the packages, runs the E2E tests, and creates a draft
   GitHub Release with generated release notes and the packages.
4. Review and publish the draft Release.
