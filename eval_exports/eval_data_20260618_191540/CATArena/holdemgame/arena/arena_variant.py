import requests
import time
import logging
import json
import uuid
import os
import socket
from config import GAME_SERVER_CONFIG, TOURNAMENT_CONFIG, AI_CONFIGS, QUICK_AI_CONFIGS, BLIND_STRUCTURE
from csv_reporter import CsvReporter

# --- Logger Setup ---
logger = logging.getLogger(__name__)
TIMEOUT = 3
class Arena:
    def __init__(self, ais, tournament_config, server_config, default_blind_structure, log_dir=None):
        self.ais = ais
        self.tournament_config = tournament_config
        self.server_config = server_config
        self.game_id = None
        self.tournament_id = f"tourney_{uuid.uuid4().hex[:6]}"
        
        # 设置日志目录
        if log_dir:
            self.log_dir = log_dir
        else:
            self.log_dir = 'magic_report'  # 默认目录
        
        # 确保日志目录存在
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            logger.info(f"Created log directory: {self.log_dir}")
        
        self.reporter = CsvReporter(self.log_dir)
        self.overall_stats = {ai['ai_id']: {
            "ai_name": ai['ai_name'],
            "wins": 0, # Now counts number of tournament wins
            "chips": 0,
            "total_actions": 0,
            "total_thinking_time": 0,
            "timeouts": 0,
            "action_errors": 0
        } for ai in self.ais}
        self.blind_structure = self._load_blind_structure(default_blind_structure)
        self.ai_statistics = {}
        self.current_round = 0
        self.round_history_files = {}

    def _load_blind_structure(self, default_structure):
        filepath = self.tournament_config.get('blind_structure_file')
        if filepath and os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    structure = json.load(f)
                    logger.info(f"Loaded blind structure from {filepath}")
                    return structure
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load or parse blind structure file {filepath}: {e}")
        logger.info("Using default blind structure.")
        return default_structure

    def _server_request(self, method, endpoint, data=None):
        url = f"{self.server_config['url']}{endpoint}"
        try:
            if method == 'GET':
                response = requests.get(url, timeout=self.server_config['timeout'])
            elif method == 'POST':
                response = requests.post(url, json=data, timeout=self.server_config['timeout'])
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Server request failed: {e}")
            return None

    def _ai_request(self, ai_config, game_state):
        start_time = time.time()
        action = {"action": "fold", "amount": 0} # Default action
        try:
            # 检查是否提供了一个玩家的手牌信息
            players_info = game_state['players']
            for player_id, player_info in players_info.items():
                if player_id == ai_config['ai_id']:
                    if player_info.get('hole_cards') == []:
                        logger.warning(f"AI {ai_config['ai_name']} is missing hole_cards in game state.")

            
            response = requests.post(f"{ai_config['url']}/action", json=game_state, timeout=TIMEOUT)
            response.raise_for_status()
            action = response.json()
            if action is None or not isinstance(action, dict):
                logger.error(f"AI {ai_config['ai_name']} returned None or invalid response.")
                self.overall_stats[ai_config['ai_id']]['action_errors'] += 1
                self.ai_statistics[ai_config['ai_id']]['rounds'][self.current_round]['http_errors'] += 1
                action = {"action": "fold", "amount": 0}
                action_name = "invalid_action"
            else:
                action_name = action.get("action", "invalid_action")
            stats_round = self.ai_statistics[ai_config['ai_id']]['rounds'][self.current_round]
            stats_round["actions"][action_name] = stats_round["actions"].get(action_name, 0) + 1

        except requests.exceptions.Timeout:
            logger.warning(f"AI {ai_config['ai_name']} timed out.")
            self.overall_stats[ai_config['ai_id']]['timeouts'] += 1
            self.ai_statistics[ai_config['ai_id']]['rounds'][self.current_round]['http_errors'] += 1
            # action is already defaulted to fold
        except requests.exceptions.RequestException as e:
            logger.error(f"AI request to {ai_config['url']} failed: {e}")
            self.ai_statistics[ai_config['ai_id']]['rounds'][self.current_round]['http_errors'] += 1
            # action is already defaulted to fold
        end_time = time.time()
        thinking_time = end_time - start_time
        self.overall_stats[ai_config['ai_id']]['total_thinking_time'] += thinking_time
        self.overall_stats[ai_config['ai_id']]['total_actions'] += 1
        return action

    def check_ai_services(self):
        logger.info("Checking AI services before starting tournament...")
        all_services_ok = True
        for ai_config in self.ais:
            host = "localhost"  # Assuming all AI services run locally
            port = ai_config.get('port')
            if not port:
                logger.error(f"AI {ai_config['ai_name']} has no port configured.")
                all_services_ok = False
                continue
            
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2)  # 2-second timeout for check
                    s.connect((host, port))
                logger.info(f"OK - AI service {ai_config['ai_name']} is responsive on port {port}.")
            except (socket.timeout, ConnectionRefusedError):
                logger.error(f"FAIL - AI service {ai_config['ai_name']} on port {port} is not reachable.")
                all_services_ok = False
        
        return all_services_ok

    def setup_new_game(self):
        blind_level = self.blind_structure['levels'][0]
        game_data = {
            "small_blind": blind_level['small_blind'],
            "big_blind": blind_level['big_blind'],
            "max_players": self.tournament_config['max_players']
        }
        game_info = self._server_request('POST', '/games', game_data)
        if not game_info:
            logger.error("Failed to create game.")
            return False
        
        self.game_id = game_info['game_id']
        logger.info(f"New game created for elimination round with ID: {self.game_id}")

        for ai in self.ais:
            player_data = {
                "player_id": ai['ai_id'],
                "name": ai['ai_name'],
                "chips": self.tournament_config['initial_chips']
            }
            res = self._server_request('POST', f'/games/{self.game_id}/players', player_data)
            if not res:
                logger.error(f"Failed to add player {ai['ai_id']}")
                return False
        
        res = self._server_request('POST', f'/games/{self.game_id}/start', {})
        if not res:
            logger.error("Failed to start game after setup.")
            return False

        return True

    def run_tournament(self):
        logger.info(f"--- Starting Tournament ({self.tournament_id}) ---")
        
        if not self.check_ai_services():
            logger.error("One or more AI services are not available. Aborting tournament.")
            return

        logger.info(f"Running {self.tournament_config['rounds']} elimination rounds.")

        for round_num in range(1, self.tournament_config['rounds'] + 1):
            self.current_round = round_num
            logger.info(f"--- Elimination Round {self.current_round} ---")

            # Initialize stats for this round
            for ai in self.ais:
                if ai['ai_id'] not in self.ai_statistics:
                    self.ai_statistics[ai['ai_id']] = {"ai_name": ai['ai_name'], "rounds": {}}
                self.ai_statistics[ai['ai_id']]['rounds'][self.current_round] = {
                    "actions": {},
                    "http_errors": 0,
                    "action_errors": 0
                }

            if not self.setup_new_game():
                logger.error(f"Failed to setup game for round {self.current_round}. Aborting tournament.")
                return
            
            self.run_elimination_game()
            self.finalize_round()

        self.finalize_tournament()

    def run_elimination_game(self):
        hand_num = 0
        current_blind_level = None
        max_hands = self.tournament_config.get('max_hands_per_round')

        while True:
            hand_num += 1
            if max_hands and hand_num > max_hands:
                logger.info(f"Round reached the maximum of {max_hands} hands. Ending round based on current chip counts.")
                break

            state = self._server_request('GET', f'/games/{self.game_id}/state')
            if not state or state.get('phase') == 'finished':
                logger.info("Elimination game finished.")
                break

            new_blind_level = self.get_blind_level(hand_num)
            if new_blind_level != current_blind_level:
                current_blind_level = new_blind_level
                logger.info(f"Hand {hand_num}: Blind level updated to {current_blind_level['small_blind']}/{current_blind_level['big_blind']}")
                self._server_request('POST', f'/games/{self.game_id}/blinds', {
                    "small_blind": current_blind_level['small_blind'],
                    "big_blind": current_blind_level['big_blind']
                })

            logger.info(f"--- Hand #{hand_num} ---")

            chip_changes, final_chips = self.play_hand()

            if final_chips:
                logger.info("--- Hand End Chip Counts ---")
                sorted_players = sorted(final_chips.items(), key=lambda item: item[1], reverse=True)
                for p_id, final_chip_count in sorted_players:
                    if p_id in self.overall_stats:
                        change = chip_changes.get(p_id, 0)
                        logger.info(f"  Player: {self.overall_stats[p_id]['ai_name']}, Chips: {final_chip_count} ({change:+}d)")
            
            if hand_num == max_hands:
                logger.info(f"Round reached the maximum of {max_hands} hands. Ending round based on current chip counts.")
                break
            
            res = self._server_request('POST', f'/games/{self.game_id}/next_hand', {})
            if not res:
                logger.info("Server indicated no next hand, ending elimination game.")
                break
            time.sleep(self.tournament_config['delay_between_hands'])

    def get_blind_level(self, hand_number):
        total_duration = 0
        for level in self.blind_structure['levels']:
            total_duration += level['duration']
            if hand_number <= total_duration:
                return level
        return self.blind_structure['levels'][-1] # Return last level if hands exceed total duration

    def play_hand(self):
        hand_over = False
        current_phase = None

        # Get initial state (no player_id needed for chip counting)
        state_before = self._server_request('GET', f'/games/{self.game_id}/state')
        if not state_before or not state_before.get('players'):
            return {}, {}
        chips_before_hand = {p['player_id']: p['chips'] for p in state_before['players'].values()}

        # Get state with player_id for AI decision making (includes hand cards)
        first_ai_id = self.ais[0]['ai_id'] if self.ais else None
        state = self._server_request('GET', f'/games/{self.game_id}/state?player_id={first_ai_id}')
        if state:
            sb_player = next((p for p in state['players'].values() if p['is_small_blind']), None)
            bb_player = next((p for p in state['players'].values() if p['is_big_blind']), None)
            if sb_player and bb_player:
                logger.info(f"Blinds: Small Blind: {sb_player['name']} ({state['small_blind']}), Big Blind: {bb_player['name']} ({state['big_blind']})")

        while not hand_over:
            state = self._server_request('GET', f'/games/{self.game_id}/state')
            current_player_id = state.get('current_player')
            state = self._server_request('GET', f'/games/{self.game_id}/state?player_id={current_player_id}')
            if not state:
                logger.error("Could not get game state.")
                break

            if state['phase'] != current_phase:
                current_phase = state['phase']
                if current_phase in ['flop', 'turn', 'river']:
                    community_cards_str = " ".join(state['community_cards'])
                    logger.info(f"--- Entering {current_phase.upper()} --- Community Cards: [{community_cards_str}]")

            if state['phase'] == 'showdown':
                hand_over = True
                logger.info("--- Showdown ---")
                continue

            current_player_id = state.get('current_player')
            if not current_player_id:
                hand_over = True
                continue
            
            if state['phase'] == 'turn':
                logger.info(f"--- Turn ---")
                

            ai_config = next((ai for ai in self.ais if ai['ai_id'] == current_player_id), None)
            action = None
            if not ai_config:
                logger.error(f"Could not find AI config for player {current_player_id}")
                action = {"action": "fold", "amount": 0}
            else:
                valid_actions = self._server_request('GET', f'/games/{self.game_id}/actions?player_id={current_player_id}')
                state['valid_actions'] = valid_actions.get('valid_actions', []) if valid_actions else []
                
                action = self._ai_request(ai_config, state)

            action_data = {"player_id": current_player_id, "action": action.get('action', 'fold'), "amount": action.get('amount', 0)}
            logger.info(f"Player {ai_config.get('ai_name', current_player_id)} attempts action: {action_data['action']} {action_data['amount']}")
            res = self._server_request('POST', f'/games/{self.game_id}/action', action_data)

            if not res:
                logger.warning(f"Action by {ai_config.get('ai_name', current_player_id)} was rejected by the server. Determining safe fallback.")
                self.ai_statistics[ai_config['ai_id']]['rounds'][self.current_round]['action_errors'] += 1
                valid_actions_response = self._server_request('GET', f'/games/{self.game_id}/actions?player_id={current_player_id}')
                valid_actions = valid_actions_response.get('valid_actions', []) if valid_actions_response else []
                
                safe_action = {"action": "fold", "amount": 0} # Default to fold
                for a in valid_actions:
                    if a['action'] == 'check':
                        safe_action = a # Prefer to check if possible
                        break
                
                logger.info(f"Forcing safe action for {ai_config.get('ai_name', current_player_id)}: {safe_action['action']}")
                final_action_data = {"player_id": current_player_id, **safe_action}
                self._server_request('POST', f'/games/{self.game_id}/action', final_action_data)

            time.sleep(self.tournament_config['delay_between_hands'])

        # Get final state (no player_id needed for chip counting)
        state_after = self._server_request('GET', f'/games/{self.game_id}/state')
        if not state_after or not state_after.get('players'):
            return {}, {}
        chips_after_hand = {p['player_id']: p['chips'] for p in state_after['players'].values()}

        chip_changes = {}
        all_player_ids = set(chips_before_hand.keys()) | set(chips_after_hand.keys())

        for p_id in all_player_ids:
            old_chips = chips_before_hand.get(p_id, 0)
            new_chips = chips_after_hand.get(p_id, 0)
            chip_changes[p_id] = new_chips - old_chips

        return chip_changes, chips_after_hand

    def finalize_round(self):
        logger.info(f"--- Elimination Round Finished ---")
        state = self._server_request('GET', f'/games/{self.game_id}/state')
        if not state or not state.get('players'):
            logger.error("Failed to get final state for the round.")
            return

        active_players = [p for p in state['players'].values() if p['chips'] > 0]
        if not active_players:
            logger.warning("No winner found for the round as no players have chips.")
            return

        # Sort players by chips to find the winner
        sorted_players = sorted(active_players, key=lambda p: p['chips'], reverse=True)
        winner = sorted_players[0]
        winner_id = winner['player_id']
        
        self.overall_stats[winner_id]['wins'] += 1
        logger.info(f"Winner of this round: {winner['name']} with {winner['chips']} chips.")

        time.sleep(1)
        # Save history for the completed round
        history_data = self._server_request('GET', f'/games/{self.game_id}/full_history')
        if history_data:
            history_filename = self.reporter.generate_history_report(self.tournament_id, history_data, round_num=self.current_round)
            self.round_history_files[self.current_round] = history_filename

    def _save_json_report(self, data, filename):
        """Saves a dictionary to a JSON file in the log directory."""
        filepath = os.path.join(self.log_dir, filename)
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=4)
            logger.info(f"Successfully saved JSON report to {filepath}")
        except (IOError, TypeError) as e:
            logger.error(f"Failed to save JSON report {filepath}: {e}")

    def finalize_tournament(self):
        logger.info("--- Final Tournament Stats ---")
        for ai_id, stats in self.overall_stats.items():
            total_actions = stats['total_actions']
            stats['avg_thinking_time'] = stats['total_thinking_time'] / total_actions if total_actions > 0 else 0
            # Sum up action_errors from all rounds
            total_action_errors = 0
            if ai_id in self.ai_statistics:
                for round_data in self.ai_statistics[ai_id]['rounds'].values():
                    total_action_errors += round_data.get('action_errors', 0)
            stats['action_errors'] = total_action_errors

        sorted_stats = sorted(self.overall_stats.items(), key=lambda item: item[1]['wins'], reverse=True)
        for ai_id, stats in sorted_stats:
            action_error_rate = (stats['action_errors'] / stats['total_actions']) * 100 if stats['total_actions'] > 0 else 0
            logger.info(f"AI: {stats['ai_name']}, Rounds Won: {stats['wins']}, Avg. Think Time: {stats['avg_thinking_time']:.2f}s, Timeouts: {stats['timeouts']}, Action Errors: {stats['action_errors']} ({action_error_rate:.2f}%)")
        
        # Generate and save the final detailed JSON report
        final_report = {
            "tournament_id": self.tournament_id,
            "config": self.tournament_config,
            "overall_stats": self.overall_stats,
            "ai_technical_statistics": self.ai_statistics,
            "round_history_files": self.round_history_files
        }
        report_filename = f"tournament_report_{self.tournament_id}.json"
        self._save_json_report(final_report, report_filename)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Texas Hold'em Arena")
    parser.add_argument('--quick', action='store_true', help='Use quick AI config for testing')
    parser.add_argument('--config', type=str, help='Path to a custom JSON config file')
    parser.add_argument('--timeout', type=int, default=3, help='Timeout for AI requests')
    parser.add_argument('--log_dir', type=str, help='Directory to save log files and reports')
    args = parser.parse_args()

    TIMEOUT = args.timeout
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Load configs
    tourney_conf = TOURNAMENT_CONFIG.copy()
    server_conf = GAME_SERVER_CONFIG.copy()
    ais = list(AI_CONFIGS)
    blind_structure = BLIND_STRUCTURE
    log_dir = None

    if args.config:
        try:
            with open(args.config, 'r') as f:
                custom_config = json.load(f)
            
            tourney_conf.update(custom_config.get('tournament', {}))
            server_conf.update(custom_config.get('game_server', {}))
            if 'timeout' in custom_config:
                TIMEOUT = custom_config['timeout']
            if 'ais' in custom_config:
                ais = custom_config['ais']
                for ai in ais:
                    if 'url' not in ai and 'port' in ai:
                        ai['url'] = f"http://localhost:{ai['port']}"
            
            # 设置日志目录为config文件的父目录下的log文件夹
            config_dir = os.path.dirname(os.path.abspath(args.config))
            log_dir = os.path.join(config_dir, 'log')
            logger.info(f"Log directory set to: {log_dir}")

        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading config file: {e}")
    elif args.quick:
        ais = QUICK_AI_CONFIGS
    
    # 如果指定了 --log_dir 参数，则覆盖之前的设置
    if args.log_dir:
        log_dir = args.log_dir
        logger.info(f"Log directory overridden to: {log_dir}")

    # Remove hands_per_game as it is no longer used in this mode
    tourney_conf.pop('hands_per_game', None)

    arena = Arena(ais, tourney_conf, server_conf, blind_structure, log_dir)
    arena.run_tournament()