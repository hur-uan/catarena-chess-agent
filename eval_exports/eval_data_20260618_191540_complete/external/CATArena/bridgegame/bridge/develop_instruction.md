# Bridge AI Development Guide (Aligned with AI Example)

This guide specifies the AI service contract and integration flow, aligned exactly with the reference AI server in `bridge/AI_example/ai_http_server.py` and the game server in `bridge/server.py`.

## Environment

- Game server default URL: `http://localhost:9030`
- Game type: 4-player Bridge (N/E/S/W), 2v2
- Phases: bidding → playing → finished

## Development Requirements

### 1. AI Service Interface Specification

Your AI must implement the following HTTP endpoints, exactly matching `AI_example`:

- Health
  - GET `/health`
  - Response: `{ "status": "healthy", "ai_id": "<id>" }`

- Info
  - GET `/info`
  - Response: `{ "ai_id": "<id>", "ai_name": "<name>", "game_server_url": "http://localhost:9030", "active_games": <int> }`

- Join Game
  - POST `/join_game`
  - Request JSON: `{ "game_id": "<game_id>", "player_id": <0..3> }`
  - Behavior: Call game server `POST /games/{game_id}/join` with `{ "player_id", "player_name" }`, then cache `active_games[game_id] = { player_id }`.
  - Response: `{ "status": "joined", "game_id": "<game_id>", "player_id": <int> }`

- Get Action
  - POST `/get_action`
  - Request JSON: `{ "game_id": "<game_id>", "game_state": { ... } }`
  - Behavior: Decide the action for current phase. Fetch legal actions from game server if needed.
  - Response: a plain action object, e.g. bidding `{ "type": "call", "call_type": "pass" }`, playing `{ "type": "play", "card": "AS" }`.
  - Error: 400 with `{ "error": "No action available" }` if no valid move.

- Leave Game
  - POST `/leave_game`
  - Request JSON: `{ "game_id": "<game_id>" }`
  - Response: `{ "status": "left", "game_id": "<game_id>" }`

- List Active Games
  - GET `/games`
  - Response: `{ "active_games": ["<game_id>", ...], "game_count": <int> }`

### 1.1 Arena Deployment & Concurrency

- Four instances per team: one per seat (N/E/S/W), typically four ports per team.
- Parallel rooms and matches: AI services must be stateless/concurrent; track multiple `game_id`s in `active_games`.
- Example ports: `50001..50004` for one team; a different range for the opponent.

### 2. Game Rule Understanding

#### Basic Rules
- **Number of Players**: 4 (North, East, South, West)
- **Partnership**: N-S vs E-W
- **Cards per Player**: 13
- **Game Phases**: Bidding → Playing

#### Bidding Rules
- **Pass**: Pass
- **Bid**: Bid (1C-7NT)
- **Double**: Double (only on opponent's bid)
- **Redouble**: Redouble (only on opponent's double)
- **Bidding Ends**: 3 consecutive passes

#### Playing Rules
- **Lead from Left**: Lead starts from declarer's left
- **Follow Suit**: Must follow suit if possible
- **Trump Highest**: Trump cards are highest, same suit compared by rank
- **Trick Winner**: Trick winner leads next trick

#### Scoring Rules
- **Contract Made**: Base points × doubling multiplier
- **Contract Failed**: Penalty points
- **Vulnerability**: Affects penalty calculation

#### Key Game Server Endpoints
```
POST /games                                  # create game
POST /games/{game_id}/join                   # join game
POST /games/{game_id}/start                  # start game
GET  /games/{game_id}/state?player_id=<id>   # per-seat state
GET  /games/{game_id}/legal_actions?player_id=<id>
POST /games/{game_id}/call                   # bidding
POST /games/{game_id}/play                   # playing
GET  /games/{game_id}/history                # history
```

### 3. Development Steps

#### Step 1: Environment Preparation
1. Create AI service file
2. Implement Flask application and basic interfaces
3. Ensure HTTP service can start correctly

#### Step 2: Source Code Analysis
1. **Carefully read `server.py`**: Understand the core logic and rules of the game
2. **Analyze `AI_example/ai_http_server.py`**: Understand the reference AI service
3. **Study API responses**: Understand various data structures through testing
4. **Understand game state**: Analyze state management in bidding and playing phases

#### Step 3: Core Algorithm Implementation
1. **Bidding Strategy**: Implement bidding algorithm based on point count and hand pattern
2. **Playing Strategy**: Implement playing algorithm based on situation
3. **Partnership Coordination**: Implement coordination strategy with partner
4. **Situation Evaluation**: Implement accurate situation evaluation algorithm

#### Step 4: Testing and Validation
1. Start game server: `python -m bridge.server --port 9030`
2. Start your AI service: Ensure your AI service runs on the specified port and correctly implements HTTP interfaces
3. Run testing: `python test_ai_client.py`

### 4. Key Development Tips

#### Algorithm Design Principles
- Implement accurate point count calculation (high card points + distribution points)
- Implement intelligent bidding strategy
- Implement efficient playing algorithm
- Consider partnership coordination and signal passing
- Optimize algorithm efficiency

#### Common AI Strategies
1. **Point Evaluation**: Calculate hand points (A=4, K=3, Q=2, J=1)
2. **Pattern Evaluation**: Evaluate hand distribution and fit potential
3. **Bidding Strategy**: Choose appropriate bids based on points and pattern
4. **Playing Strategy**: Choose optimal plays based on situation
5. **Partnership Coordination**: Coordinate with partner through signals

#### Bidding Strategy Points
- **Opening**: 13+ points to open, choose appropriate bid
- **Responding**: Choose appropriate response based on partner's bid
- **Competitive**: Choose appropriate competitive bid when opponents bid
- **Preemptive**: Use preemptive bids at appropriate times

#### Playing Strategy Points
- **Lead**: Choose appropriate opening lead
- **Follow**: Choose appropriate follow based on situation
- **Trump**: Use trump cards reasonably
- **Signals**: Pass signals to partner through plays

#### Error Handling
- Gracefully handle various abnormal situations
- Ensure AI can work normally in various situations
- Implement reasonable timeout and retry mechanisms

### 5. Performance Requirements

- **Response Time**: Each action should be completed within 10 seconds
- **Memory Usage**: Reasonably control memory usage
- **Error Handling**: Gracefully handle various abnormal situations
- **Concurrent Support**: Support participating in multiple games simultaneously

### 6. Testing Requirements

Your AI must pass the following tests:
1. Health check testing
2. Basic feature testing
3. Game rule adaptation testing
4. Bidding strategy testing
5. Playing strategy testing
6. Battle testing

### 7. Submission Requirements

Please provide:
1. Complete AI service code
2. Startup instructions
3. Algorithm explanation
4. Testing results
5. Performance analysis

## Development Tips

1. **Deep Source Code Analysis**: Carefully read `server.py` and `AI_example/ai_http_server.py` to understand specific implementations
2. **Understand Game Mechanisms**: Understand Bridge's core rules and mechanisms through source code analysis
3. **Testing-Driven Development**: First implement basic features, then gradually optimize
4. **Error Handling**: Ensure AI can work normally in various abnormal situations
5. **Performance Optimization**: Optimize algorithm efficiency while ensuring correctness

## Evaluation Standards

Your AI will be evaluated according to the following standards:
1. **Correctness**: Whether it correctly follows Bridge rules
2. **Intelligence**: Quality of AI decisions
3. **Stability**: Performance in various situations
4. **Performance**: Response speed and resource usage
5. **Code Quality**: Readability and maintainability of code

## Technical Reference

### Data Structures
- **Card Representation**: Suit (C/D/H/S) + Rank (2-9/T/J/Q/K/A)
- **Hand**: Collection of 13 cards
- **Bidding History**: Record all bidding actions
- **Playing History**: Record all playing actions
- **Game State**: Record current phase, player status, etc.

### Key Algorithms
- **Point Calculation**: High card points + distribution points
- **Bidding Evaluation**: Bidding decisions based on points and pattern
- **Playing Evaluation**: Playing decisions based on situation
- **Situation Evaluation**: Evaluate current situation and win probability

## Important Reminders

**Please carefully read the source code**: All specific implementation logic of the game is in `server.py`. Through deep source code analysis, you can:
- Understand the core logic of the game
- Learn bidding and playing rules
- Master data structure design
- Learn error handling mechanisms

**Reference Example Code**: `bridge_ai_server.py` provides a complete AI service implementation example that can serve as a reference for development.

**Bridge Specificity**: Bridge is a 4-player cooperative game that requires consideration of:
- Partnership coordination
- Signal passing
- Situation evaluation
- Risk control

Please start your development work and ensure your AI can perform excellently in this standard Bridge environment! 
