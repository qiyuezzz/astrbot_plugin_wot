from __future__ import annotations

import re

from bs4 import BeautifulSoup

from data.plugins.astrbot_plugin_wot.src.domain.report import (
    FrequentTank,
    PlayerStats,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.parsers.number_utils import (
    clean_number,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.repositories.tank_repository import (
    get_tank_info_by_name,
)


class WotBoxStatsParser:
    """Parse WotBox HTML into domain models."""

    def parse_player_stats(
        self, raw_html: str, player_name: str
    ) -> tuple[PlayerStats, list[FrequentTank]]:
        stats_data = self._init_default_stats_data(player_name)
        soup = BeautifulSoup(raw_html, "html.parser")

        self._parse_efficiency_data(soup, stats_data)
        self._parse_update_time(soup, stats_data)
        self._parse_charts_data(soup, stats_data)
        self._parse_detail_data(soup, stats_data)
        self._parse_comment_data(soup, stats_data)
        stats_data["radar_data"] = self._parse_radar_data(raw_html)

        frequent_tanks = self._parse_frequent_tanks(soup)
        return PlayerStats(**stats_data), frequent_tanks

    @staticmethod
    def _init_default_stats_data(player_name: str) -> dict:
        return {
            "name": player_name,
            "update_time": "",
            "power": "",
            "power_float": "",
            "win_rate": "",
            "total_count": "",
            "win_count": "",
            "lose_count": "",
            "hit_rate": "",
            "avg_tier": "",
            "avg_damage": "",
            "avg_exp": "",
            "avg_kill": "",
            "avg_occupy": "",
            "avg_defense": "",
            "avg_discovery": "",
            "comment": "",
            "radar_data": [],
        }

    @staticmethod
    def _parse_efficiency_data(soup: BeautifulSoup, stats_data: dict) -> None:
        other_info_div = soup.find("div", class_="other-info")
        if not other_info_div:
            return
        power_tag = other_info_div.find("span", class_="num")
        power_float_tag = other_info_div.find("span", class_="float-num")
        stats_data["power"] = power_tag.get_text(strip=True) if power_tag else ""
        stats_data["power_float"] = (
            power_float_tag.get_text(strip=True) if power_float_tag else ""
        )

    @staticmethod
    def _parse_update_time(soup: BeautifulSoup, stats_data: dict) -> None:
        title_div = soup.find("div", class_="userRecord-history__title")
        if title_div and (title_text := title_div.find("p")):
            time_text = title_text.get_text(strip=True).split("(")[0]
            if match := re.search(r"\d{4}-\d{2}-\d{2}", time_text):
                stats_data["update_time"] = match.group()

    @staticmethod
    def _parse_charts_data(soup: BeautifulSoup, stats_data: dict) -> None:
        charts_box = soup.find("div", class_="userRecord-charts")
        if not charts_box:
            return

        win_frame = charts_box.find("div", class_="userRecord-charts__winRate--frame")
        if win_frame and len(win_frame.find_all("p")) >= 2:
            stats_data["win_rate"] = win_frame.find_all("p")[1].get_text(strip=True)

        win_data = charts_box.find("div", class_="userRecord-charts__winRate--data")
        if win_data:
            total_tag = win_data.find("p", class_="total")
            if total_tag:
                stats_data["total_count"] = clean_number(
                    total_tag.get_text(), to_int=True
                )
            result_tag = win_data.find("p", class_="result")
            if result_tag:
                win_span = result_tag.find("span", class_="win")
                fail_span = result_tag.find("span", class_="fail")
                stats_data["win_count"] = (
                    clean_number(win_span.get_text(), to_int=True) if win_span else ""
                )
                stats_data["lose_count"] = (
                    clean_number(fail_span.get_text(), to_int=True) if fail_span else ""
                )

        kill_frame = charts_box.find("div", class_="userRecord-charts__killRate--frame")
        if kill_frame and len(kill_frame.find_all("p")) >= 2:
            stats_data["hit_rate"] = kill_frame.find_all("p")[1].get_text(strip=True)

        fight_level = charts_box.find(
            "div", class_="userRecord-charts__fightingRate--frame"
        )
        if fight_level and len(fight_level.find_all("p")) >= 2:
            stats_data["avg_tier"] = fight_level.find_all("p")[1].get_text(strip=True)

    @staticmethod
    def _parse_detail_data(soup: BeautifulSoup, stats_data: dict) -> None:
        detail_data = soup.find("ul", class_="userRecord-data")
        if not detail_data:
            return
        data_list = detail_data.find_all("li")
        detail_mapping = [
            ("avg_damage", 0),
            ("avg_exp", 1),
            ("avg_kill", 2),
            ("avg_occupy", 3),
            ("avg_defense", 4),
            ("avg_discovery", 5),
        ]
        for field, idx in detail_mapping:
            if len(data_list) > idx and len(data_list[idx].find_all("p")) >= 2:
                stats_data[field] = data_list[idx].find_all("p")[1].get_text(strip=True)

    @staticmethod
    def _parse_comment_data(soup: BeautifulSoup, stats_data: dict) -> None:
        comment_list = soup.find("div", class_="comment-list__text")
        if comment_list:
            texts = [
                p.get_text(strip=True)
                for p in comment_list.find_all("p")
                if p.get_text(strip=True)
            ]
            stats_data["comment"] = "\n".join(texts) if texts else ""

    @staticmethod
    def _parse_radar_data(html_content: str) -> list[int]:
        pattern = r"App\.init\(\[\s*(.*?)\s*\]\)"
        match = re.search(pattern, html_content, re.S)
        if match:
            raw_data = match.group(1)
            numbers = re.findall(r"\d+", raw_data)
            return [int(n) for n in numbers[1::2]]
        return []

    @staticmethod
    def _parse_frequent_tanks(soup: BeautifulSoup) -> list[FrequentTank]:
        frequent_tanks: list[FrequentTank] = []
        tank_list_div = soup.find_all("div", class_="user-tank__pop")
        for pop in tank_list_div:
            header = pop.find("div", class_="tank-pop__info")
            if not header:
                continue

            tank_name = (
                header.find("h3").get_text(strip=True) if header.find("h3") else ""
            )
            p_text = header.find("p").get_text(strip=True) if header.find("p") else ""
            body = pop.find("div", class_="tank-pop__body")
            body_spans = body.find_all("span", class_="data") if body else []
            if len(body_spans) < 5:
                continue

            win_rate = (
                header.find("span", class_="win num").get_text(strip=True)
                if header.find("span", class_="win num")
                else "0"
            )

            win_count = (
                re.search(r"胜(\d+)场", p_text).group(1)
                if re.search(r"胜(\d+)场", p_text)
                else "0"
            )
            avg_power = (
                re.search(r"战力：(\d+)", p_text).group(1)
                if re.search(r"战力：(\d+)", p_text)
                else "0"
            )

            tank_info = get_tank_info_by_name(tank_name)
            frequent_tank = FrequentTank(
                tank_info=tank_info,
                win_rate=win_rate,
                win_count=win_count,
                avg_power=avg_power,
                avg_damage=body_spans[0].text,
                avg_exp=body_spans[1].text,
                avg_destroy=body_spans[2].text,
                avg_credits=body_spans[3].text,
                hit_rate=body_spans[4].text,
            )
            frequent_tanks.append(frequent_tank)
        return frequent_tanks
