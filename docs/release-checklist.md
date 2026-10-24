# Publication and release checklist
- Replace README clone URL and author contact after choosing the GitHub account.
- Choose a licence and add LICENSE; no licence choice is implied here.
- Review every file and screenshot for secrets/private data, including HighByte exports.
- Create the GitHub repository, push the reviewed source and pin the repository.
- Add real HighByte/MQTT screenshots and sanitised configuration; complete pending tests.
- Resolve or explicitly document T09 before claiming the original brief is complete.
- Write the 4–6 page PDF using verified evidence, and record/upload the demo.
- On Windows, install a chosen pinned PyInstaller version in a build environment; run:
  `python -m PyInstaller --onefile --console --name uns-bioreactor-simulator src/run_simulators.py`
- Test dist/uns-bioreactor-simulator.exe on another Windows PC; build is not verified here.
- Create GitHub tag/release v1.0 and attach the executable and final PDF; keep dist/ out of Git.
- Check all public links signed out. Add CV/LinkedIn project entry and a one-page summary with final links.

Suggested future commits: add sanitised HighByte export; add measured MQTT evidence; implement tested cooling interaction; add final project PDF and demo link. Do not fabricate retrospective history.
