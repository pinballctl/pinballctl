# High Scores

Open **Control Centre → High Scores** to see final scores from completed games. Each player has a separate entry.

<img src="./media/screenshot-feature-high-scores.webp" data-source='{"url":"/login","next_url":"/highscores/","dark_mode":true,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"wait","selector":"#highscores-rows tr"}]}' alt="High Scores module with four leaderboard tabs, ranked results, and edit and remove icons">

## Choose a board

| Tab | Order |
| --- | --- |
| **All time** | Highest score first, across all retained entries |
| **This year** | Highest score first, for games finished in the current calendar year |
| **This month** | Highest score first, for games finished in the current calendar month |
| **Latest** | Most recently finished games first |

Month and year boundaries use the controller’s local time zone. Earlier results rank first when scores tie. The browser shows 25 entries per page. Use **Previous** and **Next** to move through the board. On an existing installation, PinballCTL imports available results from its saved game history and former high score list.

## Edit, remove or reset scores

- Select the **pencil** in a row to change its initials, player name or score. Leave the initials blank to display `---`.
- Select the **trash** in a row and confirm to remove that result from all four boards.
- Select **Reset** from a regular leaderboard and confirm to clear the four regular boards. Subsequent completed games populate them again.

<img src="./media/screenshot-high-scores-edit.webp" data-source='{"url":"/login","next_url":"/highscores/","dark_mode":true,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"wait","selector":"#highscores-rows tr"},{"action":"click","selector":"#highscores-rows button[aria-label=\"Edit entry\"]","wait_for":"#highscores-edit.show"}]}' alt="Edit entry drawer with initials, player name and score">

These controls change leaderboard entries. Original results remain in completed game history. Choose **Scoring** in Backup / Restore to include leaderboard entries and display settings.

## Collect initials on the backglass

1. In **High Scores → Settings**, choose how many rows to show per board, from 1 to 10. The default is five. That setting also determines how many places on the ranked boards qualify for initials.
2. In **Media**, run a compatible Godot scene such as the Zelda sample. Map the left and right flippers to `ui_left` and `ui_right`, Select to `ui_accept`, and an optional Back button to `ui_cancel`.
3. Play through the last ball. Each player with a positive score in a qualifying position on All time, This year or This month gets a prompt in player order. Latest shows recent results regardless of rank.
4. Use the flippers to change the highlighted letter and Select to confirm it. The third confirmation saves the initials. Use Back to skip a player. The prompts expire one minute after the game ends or when another game starts. Skipped and expired entries remain on the boards with dashes.

<img src="./media/screenshot-high-scores-settings.webp" data-source='{"url":"/login","next_url":"/highscores/","dark_mode":true,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"wait","selector":"#highscores-rows tr"},{"action":"click","selector":"[data-bs-target=\"#highscores-settings\"]","wait_for":"#highscores-settings.show"}]}' alt="High Scores settings drawer with the backglass rows field">

In the Zelda sample, open **The chronicles** and use the flippers to switch boards. Its attract loop shows the top three all-time results. See the [Godot walkthrough](22-godot.md) for the scene integration contract.


## Run a competition night

1. Between games, open **Competition → Manage competition**. Enter a title, choose **Start new**, and confirm. This clears the previous competition’s scores.
2. Play as normal. Completed results go to the competition board as well as the regular leaderboards. A score that qualifies on either set of boards can prompt for initials once.
3. The Zelda backglass shows your title and competition leaders in attract mode. **The chronicles** opens on the competition board when the competition starts. Use the flippers to browse the regular boards.
4. Choose **End competition** when play is finished. The browser keeps the final results and the backglass returns to the regular boards. Use **Reset competition scores** to clear just the competition board, or **Save title** to rename it and keep the scores.

<img src="./media/screenshot-high-scores-competition.webp" alt="Competition tab showing the Friday Night League leaderboard and its management controls">

Editing or removing a competition result affects that board only. Starting or resetting a competition preserves the regular leaderboards and completed game history.
