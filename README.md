# Aircraft Comparison V1.0 (FLYINGGROUP)

This repository publishes the Aircraft Comparison tool as a website (GitHub Pages) and keeps the
Market tab up to date automatically: every day a GitHub Action collects the AvBuyer jets for sale
and commits a fresh `market_data.js`. No computer has to be switched on.

The website opens with a **login page** (account + password). The tool itself is stored encrypted
in `index.html`, so without the right account and password its content cannot be read, not even
from the page source or the repository.

## What is in the repository

| Path | What it is | On the website? |
|---|---|---|
| `index.html` | Login page with the tool inside, encrypted (AES-256) | Yes |
| `market_data.js` | Market listings, rewritten daily by the Action | Yes |
| `scripts/avbuyer_feed.py` | The scraper (Python standard library only, no installs) | No |
| `scripts/reg_cache.json` | Registration per AvBuyer listing, so each detail page is read only once | No |
| `scripts/history/` | One gzipped snapshot per day (about 13 KB each) | No |
| `scripts/encrypt_tool.py` | Turns a new tool version into the encrypted `index.html` | No |
| `scripts/login_logo.png` | Logo on the login page | No |
| `.github/workflows/market-feed.yml` | The daily schedule and the website deployment | No |

## The login: what it protects and what it does not

* The tool (including the Bluebook prices) is encrypted with a key made from the account and the
  password (PBKDF2, 600,000 rounds, then AES-256-GCM). The password itself is not in any file.
* Wrong account or password: the page says so and nothing is decrypted.
* After signing in, the tool stays open for that browser tab until the tab is closed.
* `market_data.js` is **not** encrypted: it holds public AvBuyer listings only.
* It is one shared login. Anyone who knows it can open the tool, and you cannot lock out one person.
  To change the password, run `encrypt_tool.py` again with the new one and upload the new `index.html`.
* Never put the password in this repository, the README or a commit message.

Because the tool is encrypted, a **public** repository on a free plan is workable. A private
repository hides the scraper and the history as well (Pages on a private repository needs GitHub
Pro, Team or Enterprise).

## Step by step

### 1. Create the repository

1. Sign in on github.com with the account or organisation that will own the tool.
2. Top right: **+** › **New repository**.
3. Name: for example `aircraft-comparison`. Choose Public or Private (see above).
4. Tick **Add a README file** (it is replaced in step 2). Click **Create repository**.

### 2. Upload the files

1. In the new repository: **Add file** › **Upload files**.
2. Drag in `index.html`, `market_data.js`, `README.md` and the folder `scripts`
   (with `avbuyer_feed.py`, `encrypt_tool.py`, `login_logo.png`, `reg_cache.json` and the
   `history` folder inside it).
3. At the bottom: **Commit changes**.

### 3. Add the workflow file

macOS hides folders that start with a dot, so the `.github` folder is easiest to create in the browser:

1. **Add file** › **Create new file**.
2. In the name box type exactly: `.github/workflows/market-feed.yml`
   (each `/` turns into a folder as you type).
3. Paste the full content of the file `market-feed.yml` that came with this package.
4. **Commit changes**.

### 4. Allow the Action to write the data

1. **Settings** › **Actions** › **General**.
2. Under **Workflow permissions** choose **Read and write permissions**. **Save**.

(The workflow also asks for this permission itself; this setting makes sure the organisation
does not block it.)

### 5. Switch on GitHub Pages

1. **Settings** › **Pages**.
2. Under **Build and deployment** › **Source** choose **GitHub Actions**.
3. With Enterprise Cloud and a private repository: set **Visibility** to **Private** here.

### 6. First run (test)

1. Tab **Actions** › **Market feed and website** › **Run workflow** › **Run workflow**.
2. Wait 2 to 5 minutes. Both jobs, **update** and **deploy**, must show a green tick.
3. Open the job **update** › **Collect AvBuyer listings**. A good run ends with a line like
   `OK listings=278 jets_on_site=533 unmapped=120 reg_pending=0`.
4. The website address is shown under **deploy**, and in **Settings** › **Pages**:
   `https://<account>.github.io/aircraft-comparison/`
5. Open it, sign in, go to **Market** and check the date next to **Refresh**.

If **update** fails with an HTTP error or a fetch failure, AvBuyer is probably refusing GitHub's
servers. In that case keep the daily task on the Mac and let it push the file to GitHub instead
(ask Claude to set that up). Do not try to get around a block.

### 7. Daily operation

* The Action runs every day at 06:17 UTC (08:17 Brussels in summer, 07:17 in winter).
  GitHub can start scheduled runs a few minutes late.
* When something changed, it commits `market_data.js`, `scripts/reg_cache.json` and the day's
  history file, then republishes the site. Colleagues click **Refresh** or reload the page.
* Safety check: if the crawl is incomplete, or the listing count drops more than 20% compared with
  the last snapshot, nothing is written, the run is marked red and GitHub emails you. The website
  keeps showing the last good data, and the tool warns when the data is older than 36 hours.

### 8. Updating the tool later

Never upload the plain tool file: it would be readable by anyone. Encrypt it first:

1. On a Mac with Python 3: `pip3 install cryptography`
2. `python3 scripts/encrypt_tool.py --in "Aircraft Comparison V1.0.html" --out index.html`
   It asks for the account and the password (nothing is shown or stored).
3. Upload the new `index.html` (**Add file** › **Upload files**, same name, **Commit changes**).
   The workflow publishes it within a minute, without running the scraper.

Or ask Claude to deliver the encrypted `index.html` together with the new tool version.

## Good to know

* **Inactivity rule.** In a public repository, GitHub switches off scheduled workflows after 60 days
  without repository activity. If that happens you get an email; switch it back on in the Actions tab.
* **Controller.com is not included.** It blocks automated access; the Market tab keeps its search
  links for manual checks.
* **Old snapshots.** `scripts/history` grows by about 5 MB per year. Delete old files whenever you like;
  only the newest one is used, for the 20% safety check.
* **The OneDrive version keeps working.** The daily task on the Mac still updates the copy in the
  Toolkit folder. Switch it off once the website has run reliably for a while.
