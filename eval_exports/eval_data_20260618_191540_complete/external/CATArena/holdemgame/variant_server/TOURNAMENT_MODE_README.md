# Texas Hold'em Tournament Mode

## Overview

The new tournament mode implements international standard Texas Hold'em tournament rules, including:

1. **Player Elimination Mechanism**: Players are automatically eliminated when their chips reach zero.
2. **Dynamic Blind Level Increase**: The blind level increases every (initial player count × 2) hands.
3. **Chip Deduction Mechanism**: At certain blind levels, all players' chips may be forcibly deducted.
4. **Continuous Play**: The game continues until only one player remains as the winner.

## Blind Structure

The blind structure consists of 29 levels, each lasting 24 hands:

| Level | Small Blind | Big Blind | Duration    |
|-------|-------------|-----------|-------------|
| 1     | 10          | 20        | 24 hands    |
| 2     | 20          | 30        | 24 hands    |
| 3     | 20          | 40        | 24 hands    |
| 4     | 30          | 50        | 24 hands    |
| 5     | 30          | 60        | 24 hands    |
| 6     | 40          | 80        | 24 hands    |
| 7     | 50          | 100       | 24 hands    |
| 8     | 60          | 120       | 24 hands    |
| 9     | 100         | 200       | 24 hands    |
| 10    | 100         | 200       | 24 hands    |
| 11    | 150         | 250       | 24 hands    |
| 12    | 200         | 300       | 24 hands    |
| 13    | 200         | 400       | 24 hands    |
| 14    | 300         | 500       | 24 hands    |
| 15    | 300         | 600       | 24 hands    |
| 16    | 400         | 800       | 24 hands    |
| 17    | 500         | 1,000     | 24 hands    |
| 18    | 600         | 1,200     | 24 hands    |
| 19    | 1,000       | 1,500     | 24 hands    |
| 20    | 1,000       | 2,000     | 24 hands    |
| 21    | 1,500       | 2,500     | 24 hands    |
| 22    | 2,000       | 3,000     | 24 hands    |
| 23    | 2,000       | 4,000     | 24 hands    |
| 24    | 2,500       | 5,000     | 24 hands    |
| 25    | 3,000       | 6,000     | 24 hands    |
| 26    | 4,000       | 8,000     | 24 hands    |
| 27    | 5,000       | 10,000    | 24 hands    |
| 28    | 6,000       | 12,000    | 24 hands    |
| 29    | 7,500       | 15,000    | 24 hands    |

## Game Rules

### Blind Level Increase
- Each blind level lasts for 24 hands.
- After 24 hands, the blind level automatically increases to the next level.
- The current blind level information will be displayed when the level increases.

### Chip Deduction
- The current blind structure does not include a forced chip deduction mechanism.
- Players' chips are only reduced through normal game play.

### Player Elimination
- Players are automatically eliminated when their chips reach zero.
- Eliminated players do not participate in subsequent hands.
- The game continues until only one player remains.

### Game End Condition
- The game ends when only one player remains.
- That player is declared the winner.
- If all players are eliminated, there is no winner.
