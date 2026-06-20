# demo1 Advanced Bridge AI

This is an advanced Bridge AI implementation designed for competitive tournament play. The AI features strategic bidding and playing algorithms based on standard Bridge conventions.

## Features

### Strategic Bidding
- **Point Count System**: Calculates High Card Points (HCP) and distribution points
- **Opening Bids**: Opens with 13+ total points, prefers longest suits
- **Response Bidding**: Supports partner with appropriate point requirements
- **Competitive Bidding**: Adjusts strategy based on opponent actions
- **Balanced Hand Detection**: Identifies hands suitable for No Trump contracts

### Advanced Card Play
- **Opening Leads**: Strategic leads from longest suits, fourth-highest convention
- **Following Suit**: Intelligent card selection based on trick situation
- **Trump Management**: Proper use of trump cards when available
- **Partnership Coordination**: Plays high when partner is winning, low otherwise
- **Defensive Play**: Attempts to win tricks when opponents are leading

### Technical Features
- **HTTP Service**: RESTful API compatible with tournament infrastructure
- **Concurrent Games**: Supports multiple simultaneous games
- **Error Handling**: Robust error handling and fallback strategies
- **Logging**: Comprehensive logging for debugging and analysis

## Files

- `demo1_sonnet_AI.py` - Main AI service implementation
- `start_ai.sh` - Startup script (accepts port as argument)
- `test_ai.py` - Basic functionality test script
- `README.md` - This documentation

## Usage

### Starting the AI Service

```bash
bash start_ai.sh <port>
```

Example:
```bash
bash start_ai.sh 50017
```

### Health Check

```bash
curl -s http://localhost:<port>/health
```

### API Endpoints

- `GET /health` - Health check
- `GET /info` - AI information
- `POST /join_game` - Join a game
- `POST /get_action` - Get AI action for current game state
- `POST /leave_game` - Leave a game
- `GET /games` - List active games

## AI Strategy

### Bidding Strategy

1. **Opening Requirements**: 13+ total points (HCP + distribution)
2. **Suit Selection**: Prefers longest suits, then higher-ranking suits
3. **No Trump**: 12-14 HCP with balanced distribution
4. **Support**: 3+ card support with 6+ points for simple support
5. **Game Tries**: 10+ points for raising partner's suit

### Playing Strategy

1. **Opening Leads**: 
   - Fourth highest from longest suit (4+ cards)
   - Top of sequence when available
   - Avoid leading from trump suit

2. **Following Suit**:
   - Play low when partner is winning
   - Try to win when opponents are leading
   - Use lowest card that accomplishes the goal

3. **Trump Play**:
   - Trump when unable to follow suit and opponents are winning
   - Use lowest trump that wins the trick
   - Preserve high trumps when possible

4. **Discarding**:
   - Discard lowest cards from weakest suits
   - Avoid discarding from long suits

## Algorithm Details

### Hand Evaluation
- **High Card Points**: A=4, K=3, Q=2, J=1
- **Distribution Points**: Void=3, Singleton=2, Doubleton=1
- **Honor Concentration**: Penalty for honors in short suits

### Bidding Logic
- Analyzes partnership and opponent calls
- Considers vulnerability and competitive situations
- Uses standard point count requirements
- Implements basic conventions (support, game tries)

### Card Play Logic
- Tracks current trick and winning card
- Considers trump suit and partnership
- Implements basic defensive and offensive strategies
- Uses card ranking for optimal selection

## Performance

- **Response Time**: Typically < 1 second per action
- **Memory Usage**: Minimal memory footprint
- **Concurrency**: Supports multiple simultaneous games
- **Reliability**: Robust error handling and fallback strategies

## Tournament Compatibility

This AI is designed to be fully compatible with the tournament infrastructure:
- Accepts port number as command line argument
- Implements all required HTTP endpoints
- Follows the exact API specification
- Handles concurrent game participation
- Provides proper error responses

## Testing

Run the included test script to verify functionality:

```bash
python3 test_ai.py
```

This will test all major endpoints and basic game functionality.

## Author

demo1 Advanced Bridge AI
Developed for competitive Bridge tournament play.