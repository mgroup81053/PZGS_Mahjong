import discord
from datetime import datetime, timedelta, date
from threading import Lock
from time import monotonic
import logging
import math
import sys
from pathlib import Path
from discord import app_commands
import asyncio
from google.oauth2 import service_account
from googleapiclient.discovery import build


LOCAL_DATA_FILE = Path(__file__).resolve().parent / "data.txt"
KEY_FILE = Path(__file__).resolve().parent / "google_credentials.json"
SPREADSHEET_ID = (Path(__file__).resolve().parent / "spreadsheet_id.txt").read_text(encoding="utf-8-sig").strip()
DISCORD_TOKEN = (Path(__file__).resolve().parent / "discord_token.txt").read_text(encoding="utf-8-sig").strip()
RAW_SCORE_SHEET_NAME = "점수 기록용"
RANK1_SHEET_NAME = "예선전 순위표"
RANK2_SHEET_NAME = "결승전 순위표"
selection_cache = {}
score_lock = Lock()

def write_local_file(msg: str):
    with LOCAL_DATA_FILE.open("a", encoding="utf-8") as file:
        file.write(f"{msg}\n")

def get_sheets():
    credentials = service_account.Credentials.from_service_account_file(
        str(KEY_FILE),
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=credentials)


def sheet_range(cells, sheet_name):
    name = sheet_name.replace("'", "''")
    return f"'{name}'!{cells}"


def find_game(service, game_id: int):
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=sheet_range("B3:N", RAW_SCORE_SHEET_NAME),
        valueRenderOption="UNFORMATTED_VALUE"
    ).execute()

    matches = [(row, values) for row, values in enumerate(result.get("values", []), 3)
               if values and str(values[0]).strip() == str(game_id)]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise ValueError(f"경기 ID {game_id}가 중복되어 있습니다.")

    raise ValueError(f"탁 번호 {game_id}를 찾을 수 없습니다.")


def read_game(game_id: int):
    service = get_sheets()
    row_number, values = find_game(service, game_id)

    return {
        "행": row_number,
        "탁 번호": values[0],
        "날짜": values[1],
        "지역": values[2],
        "회차": values[3],
        "테이블 번호": values[4],
        "작사": values[5:9],
        "점수": values[9:13],
    }


def update_scores(game_id, scores):
    with score_lock:
        service = get_sheets()
        row, values = find_game(service, game_id)
        stored = any(v not in ("", None) for v in values[9:13])
        target = dict(spreadsheetId=SPREADSHEET_ID,
                      range=sheet_range(f"K{row}:N{row}", RAW_SCORE_SHEET_NAME))
        cells = service.spreadsheets().values()
        if scores is None:
            if not stored:
                return False
            cells.clear(**target, body={}).execute()
        else:
            if stored:
                raise ValueError("이미 점수가 기록된 경기입니다.")
            cells.update(**target, valueInputOption="RAW", body={"values": [scores]}).execute()
        return True


def date_label(value):
    try:
        day = datetime.fromisoformat(str(value)).date()
    except ValueError:
        try:
            day = date(1899, 12, 30) + timedelta(days=float(value))
        except (TypeError, ValueError, OverflowError):
            return str(value)
    return f"{day.isoformat()} ({'월화수목금토일'[day.weekday()]})"


class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)
    
    async def setup_hook(self):
        id_file = Path(__file__).resolve().parent / "server_id.txt"
        server_id = int(id_file.read_text(encoding="utf-8-sig").strip())

        guild = discord.Object(id=server_id)
        self.tree.copy_global_to(guild=guild)
        commands = await self.tree.sync(guild=guild)

        # 예전 버전이 전역에 등록했던 명령어만 정리합니다.
        for command in await self.tree.fetch_commands():
            if command.type == discord.AppCommandType.chat_input and command.name in {"add", "hello", "edit", "수정"}:
                await command.delete()
        print("등록된 명령어:", [cmd.name for cmd in commands])

    async def on_ready(self):
        print(f"로그인 완료: {self.user}")
        write_local_file(f"Server started\n")


bot = MyBot()


class TieBreakView(discord.ui.View):
    def __init__(self, players, indices):
        super().__init__(timeout=180)
        self.selected = None

        select = discord.ui.Select(
            placeholder="순위가 높은 사람을 선택",
            options=[
                discord.SelectOption(
                    label=f"{i + 1}번: {players[i]}",
                    value=str(i)
                )
                for i in indices
            ]
        )
        select.callback = self.choose
        self.add_item(select)
        self.select = select

    async def choose(self, interaction):
        await interaction.response.defer()
        self.selected = int(self.select.values[0])
        self.stop()

class RecordGameModal(discord.ui.Modal, title="점수 입력"):
    def __init__(self, game_id, players, parent):
        super().__init__()
        self.game_id = game_id
        self.players = players
        self.parent = parent

        self.a = discord.ui.TextInput(placeholder=players[0])
        self.b = discord.ui.TextInput(placeholder=players[1])
        self.c = discord.ui.TextInput(placeholder=players[2])
        self.d = discord.ui.TextInput(placeholder=players[3])

        for player, field in zip(players, (self.a, self.b, self.c, self.d)):
            self.add_item(discord.ui.Label(text=player, component=field))

    async def on_submit(self, interaction: discord.Interaction):
        players = self.players

        try:
            a, b, c, d = (
                int(field.value)
                for field in (self.a, self.b, self.c, self.d)
            )

            if any(score % 100 for score in (a, b, c, d)):
                await interaction.response.send_message("100점 단위로 입력해 주세요. 점수 입력 버튼으로 다시 시도하세요.", ephemeral=True)
                return
            if a+b+c+d != 25000*4:
                raise ZeroDivisionError


            # 동점자 처리
            scores = [a, b, c, d]
            ranks = [None] * 4

            await interaction.response.defer(
                ephemeral=True, thinking=True
            )

            next_rank = 1

            # 높은 점수부터 처리
            for score in sorted(set(scores), reverse=True):
                remaining = [
                    i for i, value in enumerate(scores)
                    if value == score
                ]

                # 동점자가 여러 명이면 순서대로 선택
                while len(remaining) > 1:
                    view = TieBreakView(
                        players=players,
                        indices=remaining,
                    )

                    await interaction.edit_original_response(
                        content=(
                            f"{score}점 동점자 중 "
                            f"**{next_rank}위**를 선택해 주세요."
                        ),
                        view=view,
                    )

                    timed_out = await view.wait()

                    if timed_out or view.selected is None:
                        await interaction.edit_original_response(
                            content="선택 시간이 초과되었습니다. 저장하지 않았습니다.",
                            view=None
                        )
                        return

                    index = view.selected
                    ranks[index] = next_rank
                    next_rank += 1
                    remaining.remove(index)

                # 혼자이거나 마지막으로 남은 사람
                ranks[remaining[0]] = next_rank
                next_rank += 1

            result = "\n".join(
                f"{players[i]}: {scores[i]}점 / {ranks[i]}위"
                for i in range(4)
            )

            for i in range(4):
                scores[i] += 0.1*(5-ranks[i])

        except ValueError:
            await interaction.response.send_message(
                "모든 칸에 정수를 입력해 주세요. 점수 입력 버튼을 눌러 다시 시도하세요.",
                ephemeral=True
            )
            return
        except ZeroDivisionError:
            await interaction.response.send_message(
                "점수의 합은 10만 점이 되어야 합니다. 점수 입력 버튼을 눌러 다시 시도하세요.",
                ephemeral=True
            )
            return

        try:
            await asyncio.to_thread(update_scores, self.game_id, scores)
        except ValueError as error:
            await interaction.edit_original_response(content=str(error), view=None)
            return
        except Exception:
            logging.exception("점수 저장 실패")
            await interaction.edit_original_response(content="점수 저장 결과를 시트에서 확인해 주세요.", view=None)
            return
        self.parent.stop()
        status = "입력 완료"
        try:
            game = self.parent.game
            if game is None:
                game = await asyncio.to_thread(read_game, self.game_id)
            announcement = (
                f"경기 기록 완료 · ID {self.game_id}\n"
                f"{date_label(game['날짜'])} / {game['지역']} / "
                f"{game['회차']}회차 / {game['테이블 번호']}번 테이블\n\n{result}"
            )
            await interaction.channel.send(
                announcement, allowed_mentions=discord.AllowedMentions.none()
            )
        except Exception:
            logging.exception("저장된 경기의 공개 알림 전송 실패")
            status = "점수는 저장되었습니다. 채널 공개 알림 전송에 실패했습니다."
        await interaction.edit_original_response(content=f"{status}\n{result}", view=None)
        write_local_file(f"{self.game_id}\n{' '.join(map(str, scores))}\n")


class NumberInputView(discord.ui.View):
    def __init__(self, game_id, players, game=None):
        super().__init__(timeout=180)
        self.game_id = game_id
        self.players = players
        self.game = game

    @discord.ui.button(
        label="점수 입력",
        style=discord.ButtonStyle.primary
    )
    async def open_modal(self, interaction, button):
        await interaction.response.send_modal(RecordGameModal(game_id=self.game_id, players=self.players, parent=self))

def read_games():
    service = get_sheets()

    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=sheet_range("B3:F", RAW_SCORE_SHEET_NAME),
        valueRenderOption="UNFORMATTED_VALUE"
    ).execute()

    games = []

    for row in result.get("values", []):
        if len(row) < 5 or any(value == "" for value in row[:5]):
            continue

        game_id, date_value, region, round_no, table_no = row[:5]

        try:
            games.append({
                "game_id": int(game_id),
                "날짜": str(date_value),
                "지역": str(region),
                "회차": str(round_no),
                "테이블 번호": str(table_no)
            })

        except (ValueError, TypeError, OverflowError):
            continue

    return games

class GameSelectView(discord.ui.View):
    # (데이터 키, 화면에 표시할 이름)
    STEPS = ("날짜", "지역", "회차", "테이블 번호")

    def __init__(self, games, interaction, removing):
        super().__init__(timeout=180)
        self.games = games
        self.removing = removing
        self.cache_key = (interaction.guild_id, interaction.user.id, removing)
        self.selected = {}
        self.step = 0
        self.busy = False
        cached = selection_cache.get(self.cache_key)
        if cached and monotonic() < cached[0]:
            _, previous_date, region, last_round = cached
            self.selected = {"날짜": previous_date, "지역": region}
            if self.filtered_games():
                self.step = 2
                if last_round and last_round.isdecimal():
                    for game in self.filtered_games():
                        value = game["회차"]
                        if value.isdecimal() and int(value) == int(last_round) + 1:
                            self.selected["회차"] = value
                            self.step = 3
                            break
            else:
                self.selected.clear()
        self.make_dropdown()

    async def interaction_check(self, interaction):
        return not self.busy and interaction.user.id == self.cache_key[1]

    async def reset(self, interaction):
        selection_cache.pop(self.cache_key, None)
        self.selected.clear()
        self.step = 0
        self.make_dropdown()
        await interaction.response.edit_message(content=self.prompt(), view=self)

    def prompt(self):
        parts = [date_label(value) if key == "날짜" else value
                 for key, value in self.selected.items()]
        return " / ".join(parts + [f"{self.STEPS[self.step]} 선택"])

    def filtered_games(self):
        return [
            game for game in self.games
            if all(
                str(game[key]) == value
                for key, value in self.selected.items()
            )
        ]

    def make_dropdown(self):
        # 현재 조건에 맞는 대진표 값만 수집하고 중복 제거
        self.values = list(dict.fromkeys(
            str(game[self.STEPS[self.step]])
            for game in self.filtered_games()
            if str(game[self.STEPS[self.step]]).strip()
        ))

        if not self.values:
            raise ValueError(f"선택할 {self.STEPS[self.step]} 항목이 없습니다.")


        if len(self.values) > 25:
            raise ValueError("이 단계의 선택지가 디스코드 제한인 25개를 초과했습니다.")
        self.clear_items()

        self.dropdown = discord.ui.Select(
            placeholder=f"{self.STEPS[self.step]} 선택",
            options=[
                discord.SelectOption(
                    label=(date_label(value) if self.step == 0 else value)[:100],
                    value=str(index)
                )
                for index, value in enumerate(self.values)
            ]
        )

        self.dropdown.callback = self.choose
        self.add_item(self.dropdown)

        if self.selected:
            button = discord.ui.Button(label="날짜·지역 다시 선택")
            button.callback = self.reset
            self.add_item(button)

    async def choose(self, interaction):
        key = self.STEPS[self.step]
        index = int(self.dropdown.values[0])
        self.selected[key] = self.values[index]

        if key == "지역":
            selection_cache[self.cache_key] = (monotonic() + 21600, self.selected["날짜"], self.selected["지역"], None)
        # 다음 선택 단계
        if self.step < len(self.STEPS) - 1:
            self.step += 1

            try:
                self.make_dropdown()
            except ValueError as error:
                self.stop()
                await interaction.response.edit_message(
                    content=str(error),
                    view=None
                )
                return

            await interaction.response.edit_message(content=self.prompt(), view=self)
            return

        matches = self.filtered_games()
        self.busy = True
        self.stop()
        if len(matches) != 1:
            await interaction.response.edit_message(content="경기를 하나로 특정할 수 없습니다.", view=None)
            return
        game_id = matches[0]["game_id"]
        expires, selected_date, region, _ = selection_cache.get(
            self.cache_key, (monotonic() + 21600, self.selected["날짜"], self.selected["지역"], None))
        if (selected_date, region) == (self.selected["날짜"], self.selected["지역"]):
            selection_cache[self.cache_key] = (expires, selected_date, region, self.selected["회차"])
        await interaction.response.edit_message(content=f"경기 {game_id} 조회 중…", view=None)
        try:
            if self.removing:
                if await asyncio.to_thread(update_scores, game_id, None):
                    message = f"경기 {game_id}의 점수를 초기화했습니다."
                else:
                    message = "기록된 점수가 없습니다."
            else:
                game = await asyncio.to_thread(read_game, game_id)
                players = game["작사"]
                if any(v not in ("", None) for v in game["점수"]):
                    message = "이미 입력된 경기입니다."
                elif len(players) != 4 or not all(players) or len(set(players)) != 4:
                    message = "선수 네 명의 명단을 확인해 주세요."
                else:
                    await interaction.edit_original_response(
                        content=f"{date_label(game['날짜'])} / {game['지역']} / {game['회차']}회차 / {game['테이블 번호']}번 테이블",
                        view=NumberInputView(game_id, players, game))
                    return
        except Exception:
            logging.exception("경기 처리 실패")
            message = "처리 결과를 시트에서 확인해 주세요."
        await interaction.edit_original_response(content=message, view=None)


async def record_game(interaction, removing=False):
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        games = await asyncio.to_thread(read_games)
        if not games:
            raise ValueError("선택할 경기가 없습니다.")
        view = GameSelectView(games, interaction, removing)
        await interaction.edit_original_response(content=view.prompt(), view=view)
    except ValueError as error:
        await interaction.edit_original_response(content=str(error), view=None)
    except Exception:
        logging.exception("경기 조회 실패")
        await interaction.edit_original_response(content="대진표 조회에 실패했습니다.", view=None)


@bot.tree.command(name="remove", description="선택한 경기 점수를 초기화합니다")
async def remove_game(interaction: discord.Interaction):
    await record_game(interaction, removing=True)


@bot.tree.command(name="record", description="점수를 기록합니다")
async def en_record_game(interaction: discord.Interaction):
    await record_game(interaction)


@bot.tree.command(name="기록", description="점수를 기록합니다")
async def ko_record_game(interaction: discord.Interaction):
    await record_game(interaction)


def read_ranking(sheet):
    result = get_sheets().spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=sheet_range("C3:E", sheet),
        valueRenderOption="UNFORMATTED_VALUE"
    ).execute()
    players = []
    for row in result.get("values", []):
        if not row or not str(row[0]).strip():
            continue
        try:
            points = float(row[1])
            count = float(row[2])
            if not math.isfinite(points) or not math.isfinite(count) or count < 0 or not count.is_integer():
                raise ValueError
        except (IndexError, TypeError, ValueError):
            raise ValueError(f"{row[0]} 선수의 포인트·시합 수를 시트에서 확인해 주세요.") from None
        players.append((str(row[0]), points, int(count)))
    # 동점이면 시트에 나온 순서를 사용합니다.
    return sorted(players, key=lambda player: player[1], reverse=True)[:10]


@bot.tree.command(name="랭킹", description="포인트 상위 10명의 이름·포인트·시합 수를 확인합니다")
@app_commands.describe(구분="조회할 순위표 (기본값: 예선)")
@app_commands.choices(구분=[
    app_commands.Choice(name="예선", value="예선"),
    app_commands.Choice(name="결승", value="결승"),
])
async def ranking(interaction: discord.Interaction, 구분: str = "예선"):
    await interaction.response.defer(ephemeral=True, thinking=True)
    sheet = RANK1_SHEET_NAME if 구분 == "예선" else RANK2_SHEET_NAME
    try:
        players = await asyncio.to_thread(read_ranking, sheet)
    except ValueError as error:
        await interaction.edit_original_response(content=str(error))
        return
    except Exception:
        logging.exception("랭킹 조회 실패")
        await interaction.edit_original_response(content="순위표를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.")
        return
    if not players:
        await interaction.edit_original_response(content=f"{구분} 순위표에 등록된 선수가 없습니다.")
        return
    embed = discord.Embed(title=f"{구분} 랭킹 · 상위 {len(players)}명")
    previous_points = None
    place = 0
    for index, (name, points, count) in enumerate(players, 1):
        if points != previous_points:
            place = index
        embed.add_field(
            name=f"{place}위 · {name}"[:256],
            value=f"{points:,.1f} P · {count}시합",
            inline=False
        )
        previous_points = points
    await interaction.edit_original_response(embed=embed)


def install_standings():
    """Install formulas in D:E only on named player rows, on explicit request."""
    api = get_sheets().spreadsheets().values()
    changes = []
    for tab, condition in [(RANK1_SHEET_NAME, "<1000"), (RANK2_SHEET_NAME, ">=1000")]:
        names = api.get(spreadsheetId=SPREADSHEET_ID,
                        range=sheet_range("C3:C", tab)).execute().get("values", [])
        for row, entry in enumerate(names, 3):
            if not entry or not str(entry[0]).strip():
                continue
            formula = f"""=IF($C{row}="","",ARRAYFORMULA(LET(
              player,$C{row},ids,'점수 기록용'!B$3:B,
              east,'점수 기록용'!G$3:G,south,'점수 기록용'!H$3:H,
              west,'점수 기록용'!I$3:I,north,'점수 기록용'!J$3:J,
              eastScore,'점수 기록용'!K$3:K,southScore,'점수 기록용'!L$3:L,
              westScore,'점수 기록용'!M$3:M,northScore,'점수 기록용'!N$3:N,
              stage,(ids<>"")*IFERROR(VALUE(ids){condition},FALSE),
              played,((east=player)+(south=player)+(west=player)+(north=player))>0,
              complete,ISNUMBER(eastScore)*ISNUMBER(southScore)*ISNUMBER(westScore)*ISNUMBER(northScore),
              eligible,stage*played*complete,
              score,IF(east=player,eastScore,IF(south=player,southScore,IF(west=player,westScore,northScore))),
              lowerCount,(eastScore<score)+(southScore<score)+(westScore<score)+(northScore<score),
              points,IF(eligible,(ROUND(score,0)-25000)/1000+10*lowerCount-15,0),
              HSTACK(ROUND(SUM(points),1),SUM(eligible)))))"""
            changes.append({"range": sheet_range(f"D{row}:E{row}", tab),
                            "values": [["".join(line.strip() for line in formula.splitlines()), ""]]})
    if changes:
        api.batchUpdate(spreadsheetId=SPREADSHEET_ID,
                        body={"valueInputOption": "USER_ENTERED", "data": changes}).execute()
    print(f"순위표 수식 적용: {len(changes)}행")


if __name__ == "__main__":
    if sys.argv[1:] == ["--install-standings"]:
        install_standings()
    elif sys.argv[1:]:
        raise SystemExit("사용법: python bot.py [--install-standings]")
    else:
        bot.run(DISCORD_TOKEN)
