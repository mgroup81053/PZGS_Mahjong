import random

# ===== 설정 =====

SEEDTEXT = "######"   # 원하는 시드값

TEAMS = [
    "###", "####", "######", "#####",
    "#", "##", "#########", "############",
]

# 특정 팀의 참가 요일 고정 (설정하지 않은 팀은 랜덤)
FIXED = {
    "###": "토",
    "####": "토",
    "##": "토",
    "###": "일",
    "####": "일",
}

# 경기가 있는 요일
days = {"토": [], "일": []}















# ===== 배정 =====

def assign_teams(teams, fixed, seed):
    capacity = 4

    if len(teams) != capacity * len(days):
        raise ValueError("팀은 4의 배수여야 합니다.")

    if len(set(teams)) != len(teams):
        raise ValueError("중복된 팀 이름이 있습니다.")

    for team, day in fixed.items():
        if team not in teams:
            raise ValueError(f"존재하지 않는 팀: {team}")
        if day not in days:
            raise ValueError(f"잘못된 요일: {day}")
        days[day].append(team)

    if any(len(group) > capacity for group in days.values()):
        raise ValueError("고정된 팀이 요일별 정원을 초과했습니다.")

    rng = random.Random(seed)

    remaining = [team for team in teams if team not in fixed]
    rng.shuffle(remaining)

    for day in days:
        vacancies = capacity - len(days[day])
        days[day].extend(remaining[:vacancies])
        remaining = remaining[vacancies:]

    for day in days:
        rng.shuffle(days[day])

    return days


if __name__ == "__main__":
    SEED = int.from_bytes(SEEDTEXT.encode("utf-8"), "big")
    TEAMS.sort()
    result = assign_teams(TEAMS, FIXED, SEED)

    for day, teams in result.items():
        print(f"{day}요일: {', '.join(teams)}")