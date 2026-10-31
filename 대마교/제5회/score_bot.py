import discord
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from pathlib import Path
from discord import app_commands
import asyncio
from google.oauth2 import service_account
from googleapiclient.discovery import build
import time

LOCAL_DATA_FILE = Path(__file__).resolve().parent / "data.txt"
KEY_FILE = Path(__file__).resolve().parent / "google_credentials.json"
SPREADSHEET_ID = (Path(__file__).resolve().parent / "spreadsheet_id.txt").read_text()
DISCORD_TOKEN = (Path(__file__).resolve().parent / "discord_token.txt").read_text()
RAW_SCORE_SHEET_NAME = "점수 기록용"
RANK1_SHEET_NAME = "예선전 순위표"
RANK2_SHEET_NAME = "결승전 순위표"
CHANNEL_ID = (Path(__file__).resolve().parent / "channel_id.txt").read_text()
예선전1일차 = "2026-12-26"
예선전2일차 = "2026-12-27"
결승전 = "2027-01-03"






# (서버 ID, 사용자 ID)별 선택 기록
GAME_SELECTION_CACHE = {}
GAME_SELECTION_TTL = 6 * 60 * 60

def write_local_file(msg: str):
    with LOCAL_DATA_FILE.open("a", encoding="utf-8") as file:
        file.write(f"{msg}\n")

def date_to_str(date: str):
    if date == 예선전1일차:
        return "예선전 1일차 (토요일)"
    elif date == 예선전2일차:
        return "예선전 2일차 (일요일)"
    else:
        return "결승전"

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

    for row_number, values in enumerate(result.get("values", []), start=3):
        if not values:
            continue

        if str(values[0]).strip() == str(game_id):
            return row_number, values

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






def find_name(service, sheet, name):
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=sheet_range("C3:E", sheet_name=sheet),
        valueRenderOption="UNFORMATTED_VALUE"
    ).execute()

    for row_number, values in enumerate(result.get("values", []), start=3):
        if not values:
            continue

        if str(values[0]).strip() == name:
            return row_number, values

    raise ValueError(f"{name} 작사를 찾을 수 없습니다.")



def write_scores(game_id: int, p1: float, p2: float, p3: float, p4: float):
    service = get_sheets()
    row_number, _ = find_game(service, game_id)

    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=sheet_range(f"K{row_number}:N{row_number}", sheet_name=RAW_SCORE_SHEET_NAME),
        valueInputOption="RAW",
        body={"values": [[p1, p2, p3, p4]]}
    ).execute()

    rank_scores(game_id, p1, p2, p3, p4)

def rank_scores(game_id, p1, p2, p3, p4):
    service = get_sheets()
    game = read_game(game_id)
    players = game["작사"]
    scores = list(map(float, game["점수"]))

    ranks = []
    sorted_scores = scores[:]; sorted_scores.sort()
    for player, score in zip(players, scores):
        ranks.append(4-sorted_scores.index(score))
    del sorted_scores

    if game_id < 1000:
        # 예선전
        sheet = RANK1_SHEET_NAME
    else:
        # 결승전
        sheet = RANK2_SHEET_NAME

    for player, score, rank in zip(players, scores, ranks):
        print(player, score, rank)
        row_number, data = find_name(service, sheet, player)
        포인트 = float(data[1])
        시합수 = int(data[2])
        if rank == 1:
            우마 = 15
        elif rank == 2:
            우마 = 5
        elif rank == 3:
            우마 = -5
        elif rank == 4:
            우마 = -15
        else:
            raise ValueError

        
        변동포인트 = (round(score)-25000)/1000 + 우마

        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=sheet_range(f"D{row_number}:E{row_number}", sheet_name=sheet),
            valueInputOption="RAW",
            body={"values": [[포인트+변동포인트, 시합수+1]]}
        ).execute()
        



















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

        print("등록된 명령어:", [cmd.name for cmd in commands])
        self.tree.clear_commands(guild=None)
        await self.tree.sync()
        print("전역 명령어 삭제 완료")

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

            if any(score % 100 != 0 for score in (a, b, c, d)):
                await interaction.response.send_message(
                    "점수는 100점 단위로 입력되어야 합니다. 점수 입력 버튼을 눌러 다시 시도하세요.",
                    ephemeral=True
                )
                return
            

            if a+b+c+d != 25000*4:
                await interaction.response.send_message(
                    "점수의 합은 10만 점이 되어야 합니다. 점수 입력 버튼을 눌러 다시 시도하세요.",
                    ephemeral=True
                )
                return



            # 동점자 처리
            scores = [a, b, c, d]
            ranks = [None] * 4

            await interaction.response.defer(
                thinking=True
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

            a, b, c, d = scores

            await interaction.edit_original_response(
                content=result,
                view=None
            )
        except ValueError:
            await interaction.response.send_message(
                "모든 칸에 정수를 입력해 주세요. 점수 입력 버튼을 눌러 다시 시도하세요.",
                ephemeral=True
            )
            return

        await interaction.edit_original_response(
            content=f"입력 완료\n{players[0]}: {round(a)}점 / {ranks[0]}위\n{players[1]}: {round(b)}점 / {ranks[1]}위\n{players[2]}: {round(c)}점 / {ranks[2]}위\n{players[3]}: {round(d)}점 / {ranks[3]}위",
        )

        self.parent.scores = [a, b, c, d]

        write_local_file(f"{self.game_id}\n{a} {b} {c} {d}\n")

        await self.parent.after_submit(interaction)



class NumberInputView(discord.ui.View):
    def __init__(self, game_id, players):
        super().__init__(timeout=180)
        self.game_id = game_id
        self.players = players

    @discord.ui.button(
        label="점수 입력",
        style=discord.ButtonStyle.primary
    )
    async def open_modal(self, interaction, button):
        await interaction.response.send_modal(RecordGameModal(game_id=self.game_id, players=self.players, parent=self))

    async def after_submit(self, interaction):
        await asyncio.to_thread(
            write_scores,
            self.game_id,
            *self.scores,
        )
















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
            if isinstance(date_value, (int, float)):
                date_text = (
                    datetime(1899, 12, 30)
                    + timedelta(days=date_value)
                ).strftime("%Y-%m-%d")
            else:
                date_text = str(date_value).strip()

            games.append({
                "game_id": int(game_id),
                "날짜": date_text,
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
    def __init__(self, games, user_id, guild_id):
        super().__init__(timeout=180)
        self.games = games
        self.user_id = user_id
        self.cache_key = (guild_id, user_id)
        self.selected = {}
        self.step = 0
        self.busy = False

        cached = GAME_SELECTION_CACHE.get(self.cache_key)

        if cached:
            valid_time = (
                time.monotonic() - cached["saved_at"]
                < GAME_SELECTION_TTL
            )

            # 기억한 날짜·지역이 현재 대진표에도 있는지 확인
            valid_game = any(
                str(game["날짜"]) == cached["날짜"]
                and str(game["지역"]) == cached["지역"]
                for game in games
            )

            if valid_time and valid_game:
                self.selected = {
                    "날짜": cached["날짜"],
                    "지역": cached["지역"]
                }
                self.step = 2  # 회차부터 선택
            else:
                GAME_SELECTION_CACHE.pop(self.cache_key, None)
        if self.step == 2:
            self.auto_select_next_round()

        self.make_dropdown()

    def filtered_games(self):
        return [
            game for game in self.games
            if all(
                str(game[key]) == value
                for key, value in self.selected.items()
            )
        ]
    async def reset_selection(self, interaction):
        GAME_SELECTION_CACHE.pop(self.cache_key, None)
        self.selected = {}
        self.step = 0
        self.make_dropdown()

        await interaction.response.edit_message(
            content="날짜를 선택해 주세요.",
            view=self
        )

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "명령어를 실행한 사람만 선택할 수 있습니다.",
                ephemeral=True
            )
            return False

        if self.busy:
            await interaction.response.send_message(
                "이미 선택이 완료되었습니다.",
                ephemeral=True
            )
            return False

        return True

    def auto_select_next_round(self):
        cached = GAME_SELECTION_CACHE.get(self.cache_key)

        if (
            not cached
            or time.monotonic() - cached["saved_at"]
                >= GAME_SELECTION_TTL
            or cached["날짜"] != self.selected.get("날짜")
            or cached["지역"] != self.selected.get("지역")
            or "회차" not in cached
        ):
            return

        try:
            target = int(cached["회차"]) + 1
        except (ValueError, TypeError):
            return

        for game in self.filtered_games():
            try:
                matches = int(str(game["회차"])) == target
            except (ValueError, TypeError):
                continue

            if matches:
                self.selected["회차"] = str(game["회차"])
                self.step = 3
                return
    
    def make_dropdown(self):
        # 현재 조건에 맞는 대진표 값만 수집하고 중복 제거
        self.values = list(dict.fromkeys(
            str(game[self.STEPS[self.step]])
            for game in self.filtered_games()
            if str(game[self.STEPS[self.step]]).strip()
        ))

        if not self.values:
            raise ValueError(f"선택할 {self.STEPS[self.step]} 항목이 없습니다.")


        self.clear_items()

        self.dropdown = discord.ui.Select(
            placeholder=f"{self.STEPS[self.step]} 선택",
            options=[
                discord.SelectOption(
                    label=value[:100],
                    value=str(index)
                )
                for index, value in enumerate(self.values)
            ]
        )

        self.dropdown.callback = self.choose
        self.add_item(self.dropdown)
        if self.selected:
            reset_button = discord.ui.Button(
                label= "처음부터 다시 선택",
                style=discord.ButtonStyle.secondary
            )
            reset_button.callback = self.reset_selection
            self.add_item(reset_button)

    def selection_text(self):
        return " / ".join(
            f"{label}: {self.selected[label]}"
            for label in self.STEPS
            if label in self.selected
        )
    async def choose(self, interaction):
        key = self.STEPS[self.step]
        index = int(self.dropdown.values[0])
        self.selected[key] = self.values[index]

        if all(
            field in self.selected
            for field in ("날짜", "지역", "회차")
        ):
            previous = GAME_SELECTION_CACHE.get(self.cache_key)

            # 날짜·지역이 같으면 기존 6시간 만료 시각 유지
            same_context = (
                previous is not None
                and previous["날짜"] == self.selected["날짜"]
                and previous["지역"] == self.selected["지역"]
                and time.monotonic() - previous["saved_at"]
                    < GAME_SELECTION_TTL
            )

            GAME_SELECTION_CACHE[self.cache_key] = {
                "날짜": self.selected["날짜"],
                "지역": self.selected["지역"],
                "회차": self.selected["회차"],
                "saved_at": (
                    previous["saved_at"]
                    if same_context
                    else time.monotonic()
                )
            }

        # 다음 선택 단계
        if self.step < len(self.STEPS) - 1:
            self.step += 1

            # 지역 선택을 마쳤으면 다음 회차 자동 선택
            if self.step == 2:
                self.auto_select_next_round()

            try:
                self.make_dropdown()
            except ValueError as error:
                self.stop()
                await interaction.response.edit_message(
                    content=str(error),
                    view=None
                )
                return

            next_label = self.STEPS[self.step]

            await interaction.response.edit_message(
                content=(
                    f"{self.selection_text()}\n"
                    f"{next_label}를 선택해 주세요."
                ),
                view=self
            )
            return

        # 모든 조건 선택 완료
        matches = self.filtered_games()

        if len(matches) != 1:
            self.stop()
            await interaction.response.edit_message(
                content=(
                    "선택한 조건의 경기가 중복되어 있습니다. "
                    "대진표를 확인해 주세요."
                ),
                view=None
            )
            return

        self.busy = True
        self.stop()
        game_id = matches[0]["game_id"]

        await interaction.response.edit_message(
            content=f"{self.selection_text()}\n선택 완료",
            view=None
        )

        await record_game_by_id(
            interaction,
            game_id=game_id
        )

async def record_game(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True, thinking=True)

    games = await asyncio.to_thread(read_games)

    if not games:
        await interaction.edit_original_response(
            content="선택할 경기가 대진표에 없습니다.",
            view=None
        )
        return
    
    
    view = GameSelectView(
        games=games,
        user_id=interaction.user.id,
        guild_id=interaction.guild_id
    )

    next_label = view.STEPS[view.step]
    summary = view.selection_text()

    content = (
        f"{summary}\n{next_label}를 선택해 주세요."
        if summary
        else f"{next_label}를 선택해 주세요."
    )

    await interaction.edit_original_response(
        content=content,
        view=view
    )


async def record_game_by_id(interaction: discord.Interaction, game_id: int): 
    
    if not interaction.response.is_done():
        await interaction.response.defer(thinking=True)
    try:
        game = await asyncio.to_thread(read_game, game_id)

        print(game["날짜"])
        print(game["지역"])
        print(game["회차"])
        print(game["테이블 번호"])
        print(game["작사"])
        print(game["점수"])

        if game["점수"]:
            await interaction.edit_original_response(
                content="이미 입력이 완료되었습니다.",
                view=None
            )
            return

        view = NumberInputView(game_id=game_id, players=game["작사"])
        await interaction.edit_original_response(
            content=f"{(game["지역"])} {game["회차"]}회전 {game["테이블 번호"]}번 테이블\n점수를 입력해 주세요.",
            view=view,
        )


        timed_out = await view.wait()
        if timed_out or view.scores is None:
            await interaction.edit_original_response(
                content="입력 시간이 초과되었습니다.",
                view=None
            )
            return
    except:
        await interaction.edit_original_response(
            content="알 수 없는 요청입니다."
        )
        return
    
@bot.tree.command(name="record", description="점수를 기록합니다")
async def en_record_game(interaction: discord.Interaction):
    await record_game(interaction)


@bot.tree.command(name="기록", description="점수를 기록합니다")
async def ko_record_game(interaction: discord.Interaction):
    await record_game(interaction)












































# @bot.tree.command(name="write", description="파일에 내용을 저장합니다")
# async def write_file(interaction: discord.Interaction, text: str):
#     with LOCAL_DATA_FILE.open("a", encoding="utf-8") as file:
#         file.write(text[:200]+"\n")

#     await interaction.response.send_message(
#         text,
#         ephemeral = True
#     )

# @bot.tree.command(name="clear", description="파일을 삭제합니다")
# async def clear_file(interaction: discord.Interaction):
#     with LOCAL_DATA_FILE.open("w", encoding="utf-8") as file:
#         file.write("")

#     await interaction.response.send_message(
#         "삭제 완료",
#         ephemeral = True
#     )


# @bot.tree.command(name="read", description="파일 내용을 읽습니다")
# async def read_file(interaction: discord.Interaction):
#     if not LOCAL_DATA_FILE.exists():
#         await interaction.response.send_message(
#             "파일이 아직 없습니다.",
#             ephemeral = True,
#         )
#         return

#     text = LOCAL_DATA_FILE.read_text(encoding="utf-8")

#     await interaction.response.send_message(
#         text or "(빈 파일)",
#         ephemeral = True,
#         allowed_mentions=discord.AllowedMentions.none(),
#     )

    


# @bot.tree.command(name="hello", description="인사합니다")
# async def hello(interaction: discord.Interaction):
#     await interaction.response.send_message(
#         f"{interaction.user.mention}님, 안녕하세요!"
#     )


# @bot.tree.command(name="add", description="두 정수를 더합니다")
# async def add(interaction: discord.Interaction, a: int, b: int):
#     await interaction.response.send_message(f"결과: {a + b}")

# @bot.tree.command(name="name", description="내 이름을 출력합니다")
# async def show_name(interaction: discord.Interaction):
#     name = interaction.user.display_name

#     if len(name) == 3:
#         message = "3글자"
#     elif len(name) < 3:
#         message = "3글자 미만"
#     else:
#         message = "3글자 초과"

#     await interaction.response.send_message(
#         f"{interaction.user.mention}님, {message}"
#     )

# @bot.tree.command(name="id", description="내 id을 출력합니다")
# async def show_id(interaction: discord.Interaction):
#     await interaction.response.send_message(
#         f"{interaction.user.id}",
#         ephemeral = True
#     )



bot.run(DISCORD_TOKEN)
