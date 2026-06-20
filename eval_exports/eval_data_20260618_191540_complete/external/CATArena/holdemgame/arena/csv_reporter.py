
import csv
import os
import datetime
import json
import logging

class CsvReporter:
    def __init__(self, report_dir='reports'):
        self.report_dir = report_dir
        if not os.path.exists(self.report_dir):
            os.makedirs(self.report_dir)

    def generate_json_report(self, tournament_id, config, stats):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.report_dir, f'tournament_report_{timestamp}.json')
        report_data = {
            "tournament_id": tournament_id,
            "timestamp": timestamp,
            "config": config,
            "results": stats
        }
        with open(filename, 'w') as f:
            json.dump(report_data, f, indent=4)

    def generate_history_report(self, tournament_id, history_data, round_num=None):
        if round_num is not None:
            filename = os.path.join(self.report_dir, f'history_{tournament_id}_round_{round_num}.json')
        else:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.report_dir, f'history_{tournament_id}_{timestamp}.json')
        
        with open(filename, 'w') as f:
            json.dump(history_data, f, indent=4)
        logging.info(f"Tournament history saved to {filename}")
        return filename
