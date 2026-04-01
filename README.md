# Qwen Code Slack Bot

Talk to Qwen Code AI from Slack — completely free, runs on your computer, no server needed.

Each Slack thread = its own conversation session (Qwen remembers everything in that thread).

```
You type in Slack
  ↓  (WebSocket — no public URL needed)
Python bot running on YOUR computer
  ↓
qwen -p "your message" --resume SESSION_ID
  ↓
Qwen AI (free credits via login — no API key)
  ↓
Reply appears in your Slack thread
```

---

## What You Need Before Starting

- A computer (Mac or Windows)
- A Slack workspace where you can create apps
- 15 minutes of setup time

---

## STEP 1: Install Node.js

Qwen Code needs Node.js to run. Think of it as a foundation that Qwen sits on top of.

### On Mac:

Open **Terminal** (press `Cmd + Space`, type "Terminal", hit Enter) and paste:

```bash
brew install node
```

> Don't have Homebrew? First install it by pasting this in Terminal:
> ```bash
> /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
> ```
> Then run `brew install node`

### On Windows:

1. Go to **https://nodejs.org**
2. Download the **LTS** version (big green button)
3. Run the installer → click Next through everything → Finish
4. **Restart your computer** after installing

### Verify it worked:

Open Terminal (Mac) or Command Prompt (Windows) and type:
```bash
node --version
```
You should see something like `v20.x.x` or higher. If you see an error, restart your terminal.

---

## STEP 2: Install Qwen Code

Now install the Qwen Code CLI. In your terminal:

### Quick Install (recommended):

**Mac / Linux:**
```bash
bash -c "$(curl -fsSL https://qwen-code-assets.oss-cn-hangzhou.aliyuncs.com/installation/install-qwen.sh)"
```

**Windows (open Command Prompt as Administrator):**
```cmd
curl -fsSL -o %TEMP%\install-qwen.bat https://qwen-code-assets.oss-cn-hangzhou.aliyuncs.com/installation/install-qwen.bat && %TEMP%\install-qwen.bat
```

### Alternative — install via npm:

```bash
npm install -g @qwen-code/qwen-code@latest
```

### Or via Homebrew (Mac only):

```bash
brew install qwen-code
```

### Verify it worked:

```bash
qwen --version
```

You should see a version number. **Restart your terminal** if it says "command not found".

---

## STEP 3: Login to Qwen (get free credits)

This is the magic part — Qwen gives you **free AI credits** just for logging in. No credit card needed.

```bash
qwen
```

This opens your web browser. Log in with your Qwen account (or create one — it's free at https://qwen.ai).

After login, close the interactive session (`Ctrl + C` or type `/exit`).

### Test that headless mode works:

```bash
qwen -p "say hello world" --output-format stream-json
```

You should see JSON output with the AI's response. If this works, you're good to go.

---

## STEP 4: Install Python

The Slack bot is written in Python.

### On Mac:

```bash
brew install python3
```

### On Windows:

1. Go to **https://python.org**
2. Download Python 3.10+ (big yellow button)
3. **IMPORTANT:** Check the box that says **"Add Python to PATH"** during install
4. Click Install → Finish

### Verify:

```bash
python3 --version
```

Should show `Python 3.10.x` or higher.

---

## STEP 5: Create the Slack App

This is the longest step, but just follow along — it's all clicking buttons.

### 5A. Create the app

1. Open **https://api.slack.com/apps** in your browser
2. Click the **"Create New App"** button (top right)
3. Choose **"From scratch"**
4. App Name: type **`QwenCode`** (or any name you want)
5. Pick your Slack workspace from the dropdown
6. Click **"Create App"**

### 5B. Turn on Socket Mode

This is what lets the bot connect without needing a server or public URL.

1. In the left sidebar, click **Settings** → **Socket Mode**
2. Toggle the switch to **ON**
3. It asks for a token name — type **`qwen-bot`**
4. Click **"Generate"**
5. You'll see a token starting with **`xapp-`**
6. **COPY THIS TOKEN** and save it somewhere (Notepad, Notes app, etc.)
   - This is your **`SLACK_APP_TOKEN`**

### 5C. Add bot permissions

1. In the left sidebar, click **OAuth & Permissions**
2. Scroll down to the **"Bot Token Scopes"** section
3. Click **"Add an OAuth Scope"** and add these one by one:
   - `app_mentions:read` — lets the bot see when someone @mentions it
   - `chat:write` — lets the bot send messages
   - `im:history` — lets the bot read DM history
   - `im:read` — lets the bot see DM channels
   - `im:write` — lets the bot send DMs
   - `reactions:read` — lets the bot see reactions
   - `reactions:write` — lets the bot add the 👀 thinking indicator
   - `users:read` — lets the bot see user display names

### 5D. Turn on event subscriptions

1. In the left sidebar, click **Event Subscriptions**
2. Toggle the switch to **ON**
3. Click **"Subscribe to bot events"** to expand it
4. Click **"Add Bot User Event"** and add these two:
   - `app_mention` — triggers when someone @QwenCode in a channel
   - `message.im` — triggers when someone DMs the bot

### 5E. Enable DMs

1. In the left sidebar, click **App Home**
2. Scroll to **"Show Tabs"**
3. Make sure **"Messages Tab"** is checked/toggled ON
4. Check the box that says **"Allow users to send Slash commands and messages from the messages tab"**

### 5F. Install the app to your workspace

1. In the left sidebar, click **Install App**
2. Click **"Install to Workspace"**
3. Click **"Allow"** on the permission screen
4. You'll see a **Bot User OAuth Token** starting with **`xoxb-`**
5. **COPY THIS TOKEN** and save it
   - This is your **`SLACK_BOT_TOKEN`**

---

## STEP 6: Download & Configure the Bot

### 6A. Download the bot files

Put all the bot files (`bot.py`, `requirements.txt`, `.env.example`) in a folder on your computer.

Or if you have git:
```bash
git clone <repo-url>
cd qwen-code-slack
```

### 6B. Install Python dependencies

Open Terminal, navigate to the folder, and run:

```bash
cd qwen-code-slack
pip3 install -r requirements.txt
```

### 6C. Create your .env file

```bash
cp .env.example .env
```

Now open the `.env` file in any text editor and paste your two tokens:

```
SLACK_BOT_TOKEN=xoxb-paste-your-bot-token-here
SLACK_APP_TOKEN=xapp-paste-your-app-token-here
```

Save the file.

---

## STEP 7: Run the Bot

```bash
python3 bot.py
```

You should see:
```
==================================================
  Qwen Code Slack Bot
==================================================
  Workspace:  /Users/you/qwen-workspace
  Mode:       Socket Mode (no public URL)
  Timeout:    300s
  Auth:       all users
==================================================
  Bot is running! Send a message in Slack.
```

**The bot is now live.** Keep this terminal window open — the bot runs as long as this is running.

---

## How to Use It

### DM the bot:
1. In Slack, click on **"Direct Messages"** in the sidebar
2. Search for **"QwenCode"** (or whatever you named it)
3. Type any message — the bot will respond

### @mention in a channel:
1. Invite the bot to a channel: type `/invite @QwenCode`
2. Type `@QwenCode how do I write a Python function?`

### Thread = conversation memory:
- Replies **in the same thread** continue the same conversation
- Qwen remembers everything you discussed in that thread
- **Start a new thread** = fresh conversation with no memory of previous threads

### Visual indicators:
- 👀 reaction appears while Qwen is thinking
- 👀 disappears when the response is ready

---

## Stopping the Bot

Press `Ctrl + C` in the terminal where the bot is running.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `qwen: command not found` | Restart your terminal. If still broken, run `npm install -g @qwen-code/qwen-code@latest` |
| `node: command not found` | Install Node.js (Step 1) and restart terminal |
| `python3: command not found` | Install Python (Step 4) and restart terminal |
| Bot doesn't respond to DMs | Go to App Home in Slack app settings → enable Messages Tab |
| Bot doesn't respond at all | Check the terminal for errors. Also check `bot.log` in the project folder |
| "Auth expired" or login errors | Run `qwen` in terminal to re-login (OAuth refreshes) |
| Timeout errors | Increase `QWEN_TIMEOUT=600` in `.env` (600 = 10 minutes) |
| Bot was working, now it's not | 1) Check terminal is still running, 2) Re-login with `qwen`, 3) Restart bot |

---

## Optional: Restrict Who Can Use the Bot

By default, anyone in your Slack workspace can use the bot. To restrict it:

1. Find user IDs: In Slack, click someone's profile → click the three dots (**...**) → **"Copy member ID"**
2. Add to `.env`:
```
AUTHORIZED_USERS=U01ABC123,U02DEF456
```
3. Restart the bot
