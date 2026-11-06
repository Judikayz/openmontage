# Branch restoration

The ZIP includes `openmontage-cloud-studio.bundle`, a Git bundle with all branch refs. Extract the ZIP, then run:

```bash
git clone openmontage-cloud-studio.bundle openmontage-cloud-studio
cd openmontage-cloud-studio
git branch -a
```

To push every branch to a new empty GitHub repository:

```bash
git remote add origin https://github.com/YOUR_ACCOUNT/openmontage-cloud-studio.git
git push origin --all
git push origin --tags
```

Branches are actual Git refs, not directories named after branches. Each tool branch contains its own Dockerfile, dependencies, worker entry point, contract and documentation.
