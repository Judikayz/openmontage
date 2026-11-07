# Branch restoration

The ZIP includes `openmontage-cloud-studio.bundle`, a Git bundle with all branch refs. Extract the ZIP, then run:

```bash
git clone openmontage-cloud-studio.bundle openmontage-cloud-studio
cd openmontage-cloud-studio
git branch -a
```

The clone creates local `main` and remote-tracking refs for the other branches. Point the existing `origin` remote at your new empty GitHub repository:

```bash
git remote set-url origin https://github.com/YOUR_ACCOUNT/openmontage-cloud-studio.git
git push origin main
git push origin refs/remotes/origin/ai-video-generation:refs/heads/ai-video-generation
git push origin refs/remotes/origin/character-consistency:refs/heads/character-consistency
git push origin refs/remotes/origin/cinematic-realism:refs/heads/cinematic-realism
git push origin refs/remotes/origin/lip-sync:refs/heads/lip-sync
git push origin refs/remotes/origin/openmontage-integration:refs/heads/openmontage-integration
```

Branches are actual Git refs, not directories named after branches. Each tool branch contains its own Dockerfile, dependencies, worker entry point, contract and documentation. The main branch includes the central dashboard, API, model library and orchestration.
