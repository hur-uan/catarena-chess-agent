# Texas Hold'em AI Development Guide

## 1. Introduction

This guide provides instructions for developing a custom AI player to compete in the Texas Hold'em tournament arena. The system is designed to be language-agnostic; as long as your AI can run as an HTTP server and adhere to the specified API, it can be integrated into the tournament.

The core architecture is simple: The **Arena** manages the tournament flow and communicates with the central **Game Server**. When it is your AI's turn to act, the Arena will send an HTTP POST request with the complete game state to your AI's designated URL and port. Your AI must then respond with a JSON object representing its chosen action.

---

## 2. Core Requirement: The AI HTTP Server

Your AI must be implemented as an HTTP server that exposes a single endpoint for decision-making.

-   **Endpoint**: `POST /action`
-   **Content-Type**: `application/json`

### 2.1. Request Body: The `game_state` Object

When it is your AI's turn, the Arena will send a `POST` request to `http://<your_ai_host>:<your_ai_port>/action`. The body of this request will be a JSON object containing the complete state of the game. Your AI should use this information to make a decision.

Here is the structure of the `game_state` object:

```json
{
  "game_id": "holdem_a8168c",
  "phase": "preflop", // Current phase: 'preflop', 'flop', 'turn', 'river'
  "hand_number": 1,
  "pot": 50,
  "community_cards": [], // List of community cards, e.g., ["Ks", "5d", "Td"]
  "current_bet": 20, // The highest bet amount in the current street
  "min_raise": 20, // The minimum amount for a valid raise
  "current_player": "your_ai_id", // The ID of the player whose turn it is (this will be your AI's ID)
  "players": {
    "player1_id": {
      "player_id": "player1_id",
      "name": "Alice",
      "chips": 980,
      "hole_cards": [], // Opponent's hole cards are not visible
      "state": "active", // Player state: 'active', 'folded', 'all_in', 'out'
      "current_bet": 20, // Bet amount in the current street
      "is_dealer": false,
      "is_small_blind": true,
      "is_big_blind": false
    },
    "your_ai_id": {
      "player_id": "your_ai_id",
      "name": "MyGreatAI",
      "chips": 1000,
      "hole_cards": ["As", "Kh"], // Your AI's hole cards ARE visible here
      "state": "active",
      "current_bet": 0,
      "is_dealer": false,
      "is_small_blind": false,
      "is_big_blind": false
    }
    // ... other players
  },
  "action_history": [ // History of actions in the current hand
    {"player_id": "player1_id", "action": "raise", "amount": 20, "phase": "preflop"}
  ],
  "dealer_index": 0,
  "small_blind": 10,
  "big_blind": 20,
  "valid_actions": [ // A crucial list of all legal moves your AI can make
    {"action": "fold", "amount": 0},
    {"action": "call", "amount": 20},
    {"action": "raise", "amount": {"min": 40, "max": 1000}},
    {"action": "all_in", "amount": 1000}
  ]
}
```

### 2.2. Response Body: Your AI's Action

Your AI server must respond with a JSON object specifying the chosen action. The response must have a `200 OK` status code.

The structure of the response JSON is as follows:

```json
{
  "action": "raise",
  "amount": 50
}
```

-   **`action` (string, required)**: One of the valid action names: `"fold"`, `"check"`, `"call"`, `"raise"`, `"all_in"`.
-   **`amount` (integer, required)**: The amount associated with the action.
    -   For `fold` and `check`, this should be `0`.
    -   For `call`, this should be the amount required to call.
    -   For `raise`, this must be the **total bet amount for the street**, not the additional amount to raise. For example, if the current bet is 20 and you want to raise by 30, the `amount` should be `50`.

**Note**: The easiest way to ensure your action is valid is to choose one of the objects from the `valid_actions` list provided in the request and return it.

--- 

## 3. Data Formats

-   **Cards**: Cards are represented as a two-character string. The first character is the rank, and the second is the suit.
    -   **Ranks**: `2`, `3`, `4`, `5`, `6`, `7`, `8`, `9`, `T` (10), `J` (Jack), `Q` (Queen), `K` (King), `A` (Ace).
    -   **Suits**: `s` (spades ♠), `h` (hearts ♥), `d` (diamonds ♦), `c` (clubs ♣).
    -   *Example*: `"As"` is the Ace of Spades. `"Td"` is the 10 of Diamonds.

--- 

## 4. Quick Start: A Minimal Python AI

Here is a simple AI implementation using Python and the Flask web framework. It demonstrates the basic structure and logic required. This AI makes a random valid move.

You can find this example at `arena/AI_example/ai_http_server.py`.

## 4. Quick Start: A Minimal JavaScript AI

Here is a simple AI implementation using JavaScript and the Express.js web framework. It demonstrates the basic structure and logic required. This AI makes a simple probability-based decision.

You can find this example at `arena/AI_example_JS/ai_http_server.js`.

--- 

## 5. Integrating Your AI into a Tournament

Once your AI server is ready, you need to tell the Arena about it.

1.  **Find a configuration file** or create a new one. A good starting point is `arena/configs/tournament_test.json`.
2.  **Add your AI** to the `"ais"` list in the JSON configuration file. Each AI needs an entry with a unique `ai_id` and `port`.

    ```json
    {
      "game_server": {
        "url": "http://localhost:9012"
      },
      "tournament": {
        "rounds": 5
      },
      "ais": [
        {
          "ai_id": "alpha_bot",
          "ai_name": "AlphaBot",
          "port": 31010
        },
        {
          "ai_id": "my_new_ai",
          "ai_name": "My Awesome AI",
          "port": 5000, // The port your AI server is listening on
          "description": "An AI that will win everything."
        }
      ]
    }
    ```

3.  **Run your AI server** in a terminal.
4.  **Run the Arena** with your chosen config file.

--- 

## 6. Tournament Mode

The system supports both regular game mode and tournament mode. In tournament mode:

- **Player Elimination**: Players are automatically eliminated when their chips reach zero
- **Dynamic Blind Structure**: Blinds increase every 24 hands according to a predefined structure
- **Continuous Play**: The game continues until only one player remains as the winner
- **29 Blind Levels**: From 10/20 to 7500/15000, each level lasting 24 hands

For detailed tournament rules, see `TOURNAMENT_MODE_README.md`.

---

## 7. Important Rules and Considerations

-   **Timeout**: The Arena will wait a maximum of **3 seconds** for a response from your AI. If your AI fails to respond in time, it will be **forced to fold** for that turn, and a timeout will be logged against it.
-   **Invalid Actions**: If your AI returns an action that is not currently legal (e.g., checking when a bet is required, raising an invalid amount), the Arena will override the action and **force a safe move** (`check` if possible, otherwise `fold`). This prevents the tournament from crashing but is a sign of a bug in your AI.
-   **Statelessness**: Your AI should be stateless. All the information needed to make a decision is provided in the `game_state` object of each request. You should not rely on storing information from previous hands, as the server manages the state.
-   **Logging**: It is highly recommended to add detailed logging to your own AI server. Log the game state you receive and the action you decide to return. This will be invaluable for debugging your AI's behavior.