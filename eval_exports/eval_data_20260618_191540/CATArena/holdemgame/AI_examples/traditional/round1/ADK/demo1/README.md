# Demo1 AI - Advanced Texas Hold'em AI

## Overview

This is a sophisticated Texas Hold'em AI implementing advanced poker strategies designed for competitive tournament play. The AI combines mathematical analysis, opponent modeling, and strategic decision-making to maximize performance.

## Key Features

### 1. Hand Strength Evaluation
- **Pre-flop**: Uses modified Chen formula with position adjustments
- **Post-flop**: Comprehensive hand ranking with drawing potential
- **Dynamic evaluation**: Adapts to board texture and opponent count

### 2. Advanced Strategy Components
- **Position awareness**: Early, middle, late position adjustments
- **Pot odds calculation**: Mathematical decision-making foundation
- **Implied odds**: Future betting rounds consideration
- **Win probability estimation**: Monte Carlo-based probability assessment

### 3. Opponent Modeling
- **VPIP tracking**: Voluntarily Put money In Pot percentage
- **PFR analysis**: Pre-Flop Raise frequency
- **Aggression factor**: Betting pattern analysis
- **Tendency classification**: Tight, loose, aggressive, passive

### 4. Betting Strategy
- **Value betting**: Optimal sizing for strong hands
- **Bluffing**: Strategic deception with proper frequency
- **Semi-bluffing**: Betting with drawing hands
- **Pot control**: Managing pot size with marginal hands

### 5. Tournament Adaptations
- **Stack size awareness**: Adjusts play based on chip count
- **Blind level consideration**: Adapts to increasing blinds
- **Bubble play**: Conservative approach near elimination
- **ICM considerations**: Independent Chip Model awareness

## AI Decision Process

1. **Game State Analysis**
   - Parse current game situation
   - Update opponent statistics
   - Evaluate position and stack sizes

2. **Hand Evaluation**
   - Calculate hand strength (0.0-1.0 scale)
   - Estimate win probability against opponents
   - Consider drawing potential

3. **Strategic Decision**
   - Apply position-based strategy
   - Calculate pot odds and implied odds
   - Consider opponent tendencies
   - Determine optimal action and sizing

4. **Risk Management**
   - Bankroll preservation
   - Variance minimization
   - Tournament survival considerations

## Technical Implementation

### Core Classes
- `PokerAI`: Main AI engine with decision-making logic
- Hand evaluation algorithms
- Opponent modeling system
- Statistical tracking

### Key Methods
- `evaluate_hand_strength()`: Hand strength calculation
- `estimate_win_probability()`: Monte Carlo simulation
- `analyze_position()`: Position-based adjustments
- `calculate_bet_size()`: Optimal sizing algorithms
- `make_decision()`: Main decision engine

### API Endpoints
- `POST /action`: Main decision endpoint
- `GET /health`: Health check
- `GET /stats`: AI statistics and opponent data

## Usage

### Starting the AI
```bash
bash start_ai.sh <port>
```

### Health Check
```bash
curl -s http://localhost:<port>/health
```

### Statistics
```bash
curl -s http://localhost:<port>/stats
```

## Strategy Highlights

### Pre-flop Strategy
- **Premium hands** (AA, KK, QQ, AK): Aggressive play
- **Strong hands** (99+, AQ, KQ suited): Position-dependent
- **Marginal hands**: Tight-aggressive approach
- **Speculative hands**: Late position only

### Post-flop Strategy
- **Strong hands**: Value betting with optimal sizing
- **Drawing hands**: Semi-bluffing and pot odds consideration
- **Marginal hands**: Pot control and position play
- **Weak hands**: Fold or strategic bluffs

### Opponent Adaptation
- **Tight players**: Steal blinds, value bet thinly
- **Loose players**: Tighten up, value bet wider
- **Aggressive players**: Trap with strong hands
- **Passive players**: Bet for value, avoid bluffs

### Tournament Considerations
- **Early stages**: Tight-aggressive, build stack
- **Middle stages**: Balanced aggression, position play
- **Late stages**: ICM awareness, survival mode
- **Bubble play**: Conservative, avoid marginal spots

## Performance Optimizations

1. **Efficient algorithms**: Fast hand evaluation and probability calculation
2. **Memory management**: Optimal opponent data storage
3. **Error handling**: Robust fallback mechanisms
4. **Logging**: Comprehensive decision tracking

## Competitive Advantages

1. **Mathematical foundation**: Solid pot odds and probability calculations
2. **Adaptive strategy**: Adjusts to opponent tendencies
3. **Position awareness**: Exploits positional advantages
4. **Tournament optimization**: Designed for elimination format
5. **Risk management**: Balanced aggression with survival instincts

This AI is designed to be highly competitive in tournament settings while maintaining mathematical soundness and strategic depth.