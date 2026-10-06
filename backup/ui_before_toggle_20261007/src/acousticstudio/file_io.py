# -*- coding: utf-8 -*-
"""프로젝트 파일 저장/불러오기 모듈"""
import json


def save_project(filepath: str, state_dict: dict) -> None:
    """프로젝트 상태를 JSON 파일로 저장합니다."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(state_dict, f, indent=4, ensure_ascii=False)


def load_project(filepath: str) -> dict:
    """JSON 파일에서 프로젝트 상태를 불러옵니다."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)
