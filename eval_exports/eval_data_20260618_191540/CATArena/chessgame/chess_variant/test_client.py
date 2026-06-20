#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json


class ChessTestClient:
    def __init__(self, base_url="http://localhost:9021"):
        self.base_url = base_url

    def create_game(self, player_white="Player1", player_black="Player2", **kwargs):
        url = f"{self.base_url}/games"
        data = {"player_white": player_white, "player_black": player_black}
        data.update(kwargs)
        r = requests.post(url, json=data)
        return r.json(), r.status_code

    def get_state(self, game_id: str):
        url = f"{self.base_url}/games/{game_id}/state"
        r = requests.get(url)
        return r.json(), r.status_code

    def get_legal_moves(self, game_id: str):
        url = f"{self.base_url}/games/{game_id}/legal_moves"
        r = requests.get(url)
        return r.json(), r.status_code

    def move(self, game_id: str, player: str, move: str):
        url = f"{self.base_url}/games/{game_id}/move"
        r = requests.post(url, json={"player": player, "move": move})
        return r.json(), r.status_code


def main():
    client = ChessTestClient()

    # 1. 创建对局，固定 seed 便于复现
    game, status = client.create_game("Alpha", "Beta", seed=1234)
    print("创建对局:", status)
    print(json.dumps(game, indent=2, ensure_ascii=False))
    if status != 201:
        return

    gid = game["game_id"]

    # 2. 初始状态
    state, _ = client.get_state(gid)
    print("\n初始状态:")
    print(json.dumps(state, indent=2, ensure_ascii=False))

    # 3. 获取合法步
    legal, _ = client.get_legal_moves(gid)
    print("\n合法步(前10):", [m["uci"] for m in legal["legal_moves"][:10]])

    # 4. 获取游戏信息
    print("游戏信息:", state.get("game_info", {}))

    # 简单策略：直接走第一步合法步
    if legal["legal_moves"]:
        first = legal["legal_moves"][0]["uci"]
        res, code = client.move(gid, state["current_player"], first)
        print("\n第1步: ", code)
        print(json.dumps(res, indent=2, ensure_ascii=False))

        # 检查是否有额外移动机会
        if res.get("new_state", {}).get("extra_move_available"):
            legal2, _ = client.get_legal_moves(gid)
            print("\n额外合法步:", [m["uci"] for m in legal2["legal_moves"]])
            if legal2["legal_moves"]:
                second = legal2["legal_moves"][0]["uci"]
                res2, code2 = client.move(gid, res["new_state"]["current_player"], second)
                print("\n第2步: ", code2)
                print(json.dumps(res2, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()


