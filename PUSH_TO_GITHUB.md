# Push vibeathon code to GitHub (Vahini333/oncomap)

**Note:** The GitHub Desktop installer is in your Downloads folder: `C:\Users\madhu\Downloads\GitHubDesktopSetup-x64.exe`. Run it once to install GitHub Desktop if you haven't already. The app installs to your user AppData folder (not in Downloads).

---

## Option A: Using GitHub Desktop (easiest if you have it)

1. Open **GitHub Desktop**.
2. **File → Add Local Repository**.
3. Choose folder: `c:\Users\madhu\Downloads\vibeathon`.
4. If it says "not a Git repository", click **Create a repository**:
   - Name: `oncomap` (or leave as vibeathon)
   - Local path: `c:\Users\madhu\Downloads\vibeathon` (parent folder) so the repo is **vibeathon** inside, or choose `c:\Users\madhu\Downloads` and name the repo `vibeathon` so the folder name matches.
   - Better: choose **Local path** `c:\Users\madhu\Downloads` and **Name** `vibeathon`, then move/copy the vibeathon folder contents into the new repo.  
   **Simpler:** Leave path as `c:\Users\madhu\Downloads\vibeathon`, name repo `oncomap`, and let it "create repository" there (it will add a .git inside vibeathon).
5. In GitHub Desktop: **Repository → Repository Settings → Remote**. Set **Primary remote repository (origin)** to:  
   `https://github.com/Vahini333/oncomap.git`
6. Write a summary (e.g. "Add vibeathon code") and click **Commit to main**.
7. Click **Push origin** to push to GitHub.

---

## Option B: Using Git Bash (after installing "Git for Windows")

1. Close Cursor and open **Git Bash** from the Start menu (search "Git Bash").
2. Run:

```bash
cd /c/Users/madhu/Downloads/vibeathon
git init
git remote add origin https://github.com/Vahini333/oncomap.git
git add .
git commit -m "Add vibeathon: VCF upload, PDAC report, template PDF"
git branch -M main
git push -u origin main
```

3. Sign in when asked (use a **Personal Access Token** as password if needed: GitHub → Settings → Developer settings → Personal access tokens).

---

## Option C: From Cursor terminal (after Git is in PATH)

1. Restart Cursor so it picks up Git from the new install.
2. In the terminal:

```powershell
cd c:\Users\madhu\Downloads\vibeathon
git init
git remote add origin https://github.com/Vahini333/oncomap.git
git add .
git commit -m "Add vibeathon: VCF upload, PDAC report, template PDF"
git branch -M main
git push -u origin main
```

---

Your repo: https://github.com/Vahini333/oncomap
