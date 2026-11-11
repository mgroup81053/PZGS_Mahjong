"""마작 대회 참가 명단 PNG 생성기 (Python 3.9+, Pillow).
설치: python -m pip install Pillow
실행: python roster_image_generator.py
외부 명단: python roster_image_generator.py --data teams.json --output roster.png
글꼴 지정: python roster_image_generator.py --font /path/to/KoreanFont.ttf

같은 폴더의 teams.json을 수정하세요. 토/일 각각 4팀, 팀마다 정확히 4자리입니다.
"팀원표시": true로 켜고 false로 끕니다. 생략하면 기존처럼 공석 수만 표시합니다.
ON일 때 모든 팀에 4자리 "팀원" 배열을 입력하세요.
예: "팀원": ["김민준", "佐藤さくら", "박지훈", null] (null 또는 빈 문자열은 공석)
최초 버전의 {"이름": "김민준", "공석": false} 형식도 지원합니다.
팀원이 있으면 공석 수를 자동 계산합니다. "공석"도 지정하면 계산 결과와 같아야 합니다.
OFF에서는 기존처럼 "공석": 0~4만 입력해도 됩니다.
배열에 입력한 순서대로 해당 요일에 배치됩니다. 공석 0자리도 명시적으로 표시합니다.
랜덤참가는 위 팀과 별도의 대기 인원이며, 다음 4인 배수까지의 부족 인원을 계산합니다.
"""
import argparse
import json
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


CONFIG = json.loads(
    Path(__file__).with_name("teams.json").read_text(encoding="utf-8-sig")
)


def member_slots(team):
    """4자리 명단을 이름 또는 None(공석)으로 변환합니다. 입력은 변경하지 않습니다."""
    members = team['팀원']
    label = team.get('팀명', '팀')
    if not isinstance(members, list) or len(members) != 4:
        raise ValueError(f'{label}: 팀원은 공석 포함 정확히 4자리여야 합니다.')
    result = []
    for member in members:
        if isinstance(member, dict):
            if type(member.get('공석')) is not bool:
                raise ValueError(f'{label}: 팀원 공석 여부는 true/false여야 합니다.')
            if member['공석']:
                result.append(None)
                continue
            name = member.get('이름')
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f'{label}: 공석이 아닌 팀원의 이름을 입력하세요.')
        elif member is None or isinstance(member, str):
            name = member
            if name is None or not name.strip():
                result.append(None)
                continue
        else:
            raise ValueError(f'{label}: 팀원은 이름 문자열, null 또는 이름/공석 객체여야 합니다.')
        if '\n' in name or '\r' in name:
            raise ValueError(f'{label}: 이름은 한 줄로 입력하세요.')
        result.append(name)
    return result


def vacancy_count(team):
    return member_slots(team).count(None) if '팀원' in team else team['공석']


def validate(config):
    def nonempty(value, label):
        if not isinstance(value, str) or not value.strip() or '\n' in value or '\r' in value:
            raise ValueError(f'{label}: 비어 있지 않은 한 줄 문자열을 입력하세요.')
    if not isinstance(config, dict):
        raise ValueError('설정은 JSON 객체여야 합니다.')
    if type(config.get('팀원표시', False)) is not bool:
        raise ValueError('팀원표시는 true 또는 false여야 합니다.')
    nonempty(config.get('제목'), '제목')
    if not isinstance(config.get('부제', ''), str):
        raise ValueError('부제는 문자열이어야 합니다.')
    if type(config.get('랜덤참가', 0)) is not int or config.get('랜덤참가', 0) < 0:
        raise ValueError('랜덤참가는 0 이상의 정수여야 합니다.')
    teams = config.get('팀')
    if not isinstance(teams, list) or len(teams) != 8:
        raise ValueError('전체 팀은 정확히 8개여야 합니다.')
    for t in teams:
        if not isinstance(t, dict):
            raise ValueError('각 팀은 JSON 객체여야 합니다.')
        if t.get('요일') not in ('토요일', '일요일'):
            raise ValueError('요일은 토요일 또는 일요일이어야 합니다.')
        nonempty(t.get('팀명'), '팀명')
        if '공석' in t and (type(t['공석']) is not int or not 0 <= t['공석'] <= 4):
            raise ValueError(f"{t['팀명']}: 공석은 0부터 4까지의 정수여야 합니다.")
        if '팀원' in t:
            actual = member_slots(t).count(None)
            if '공석' in t and t['공석'] != actual:
                raise ValueError(f"{t['팀명']}: 공석 수({t['공석']})와 팀원 명단의 공석 수({actual})가 다릅니다.")
        elif config.get('팀원표시', False):
            raise ValueError(f"{t['팀명']}: 팀원표시가 true이면 4자리 팀원 명단이 필요합니다.")
        elif '공석' not in t:
            raise ValueError(f"{t['팀명']}: 공석 수 또는 팀원 명단을 입력하세요.")
    for day in ('토요일', '일요일'):
        if sum(t['요일'] == day for t in teams) != 4:
            raise ValueError(f'{day}에는 정확히 4팀이 필요합니다.')

def find_font(explicit=None):
    font_path = (
        Path(explicit)
        if explicit
        else Path(__file__).resolve().parent / "NotoSansCJKkr-Regular.otf"
    )

    if not font_path.is_file():
        raise ValueError(f"글꼴 파일을 찾을 수 없습니다: {font_path}")

    return str(font_path)

def render(config, output='mahjong_example.png', font_path=None):
    validate(config)
    font_path = find_font(font_path)
    # 설계도: 요일별 2×2 팀 카드 + 하단 랜덤 참가 현황.
    show_members = config.get('팀원표시', False)
    card_height = 390 if show_members else 270
    extra = 2 * (card_height - 270)
    im = Image.new('RGB', (1800, 1240 + extra), '#F4F3ED')
    d = ImageDraw.Draw(im)
    ink, muted = '#173C37', '#73817B'

    def text(value, x, y, size, color=ink, width=None, center=False):
        value = str(value)
        while True:
            f = ImageFont.truetype(font_path, size)
            box = d.textbbox((0, 0), value, font=f)
            tw = box[2] - box[0]
            if width is None or tw <= width:
                break
            size -= 1
            if size < 16:
                raise ValueError(f'표시 공간에 비해 글자가 너무 깁니다: {value}')
        d.text((x - tw / 2 if center else x, y), value, font=f, fill=color, anchor='lt')

    text('MAHJONG / WEEKEND TOURNAMENT', 68, 40, 20, muted)
    text(config['제목'], 64, 83, 52, ink, 1650)
    text(config.get('부제', ''), 68, 161, 24, muted, 1650)
    d.rounded_rectangle((64, 224, 1736, 1020+extra), radius=24, fill='#FFFFFF', outline='#CED8CE', width=2)
    d.line((900, 244, 900, 999+extra), fill='#CED8CE', width=2)
    d.line((88, 355, 1712, 355), fill='#CED8CE', width=2)

    for col, day in enumerate(('토요일', '일요일')):
        left = 64 + col * 836
        accent = '#246A56' if col == 0 else '#3D647E'
        teams = [t for t in config['팀'] if t['요일'] == day]
        vacant = sum(vacancy_count(t) for t in teams)
        text(day, left+418, 250, 42, accent, center=True)
        text(f'4팀 · 공석 {vacant}자리', left+418, 311, 21, muted, center=True)
        for i, team in enumerate(teams):
            x, y = left+38+(i%2)*400, 388+(i//2)*(card_height+34)
            count = vacancy_count(team)
            d.rounded_rectangle((x, y, x+360, y+card_height), radius=18, fill='#FAFBF8', outline='#DFE5DB', width=2)
            d.rounded_rectangle((x+20, y+20, x+71, y+58), radius=8, fill=accent)
            text(f'{i+1:02}', x+45, y+28, 21, '#FFFFFF', center=True)
            text(team['팀명'], x+180, y+87, 34, ink, 312, center=True)
            if show_members:
                for slot, name in enumerate(member_slots(team)):
                    sy = y + 140 + slot * 47
                    bg, fg = ('#FFF0DF', '#AA5929') if name is None else ('#E8EFE7', ink)
                    d.rounded_rectangle((x+22, sy, x+338, sy+39), radius=8, fill=bg)
                    text(str(slot+1), x+35, sy+10, 17, muted)
                    text('공석' if name is None else name, x+66, sy+7, 25, fg, 252)
                text(f'공석 {count}자리', x+180, y+348, 22, muted, center=True)
            else:
                bg, fg = ('#FFF0DF', '#AA5929') if count else ('#E8EFE7', '#426454')
                d.rounded_rectangle((x+22, y+160, x+338, y+242), radius=12, fill=bg)
                text(f'공석 {count}자리', x+180, y+182, 35, fg, 280, center=True)

    random_count = config.get('랜덤참가', 0)
    # 랜덤 참가자는 위 8팀과 별도의 대기 인원. 다음 4인 배수까지 부족 인원.
    shortage = (-random_count) % 4
    d.rounded_rectangle((64, 1050+extra, 1736, 1168+extra), radius=18, fill=ink)
    text('랜덤 참가', 94, 1089+extra, 29, '#D4E3D8')
    text(f'{random_count}명', 277, 1081+extra, 43, '#FFFFFF', 260)
    label = f'4인 팀 구성까지 {shortage}명 부족' if shortage else '4인 팀 구성 가능' if random_count else '대기 인원 없음'
    text(label, 580, 1091+extra, 29, '#E6D1AC', 1080)
    text('팀당 정원 4명 · 주황색은 공석' if show_members else '팀당 정원 4명 · 주황색은 공석이 있는 팀', 68, 1194+extra, 19, muted)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    im.save(output, format='PNG')
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--data', help='UTF-8 JSON 명단 (생략하면 코드 상단 CONFIG 사용)')
    p.add_argument('--output', default='mahjong_example.png', help='저장할 PNG 경로')
    p.add_argument('--font', help='한글 TTF/OTF/TTC 파일 경로')
    p.add_argument('--export-json', help='기본 명단을 JSON으로 저장하고 종료')
    args = p.parse_args()
    try:
        if args.export_json:
            Path(args.export_json).write_text(json.dumps(CONFIG, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'명단 저장: {args.export_json}')
            return
        config = json.loads(Path(args.data).read_text(encoding='utf-8-sig')) if args.data else CONFIG
        print(f'이미지 저장: {render(config, args.output, args.font)}')
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as e:
        p.exit(1, f'오류: {e}\n')


if __name__ == '__main__':
    main()
