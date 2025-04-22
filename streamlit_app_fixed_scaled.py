import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model

st.set_page_config(page_title="שיבוץ מתמחים", layout="wide")
st.title("📅 אפליקציית שיבוץ רופאים מתמחים למחלקת ילדים")

st.markdown("""
בחר את מספר המתמחים, הרץ את האופטימיזציה, וייצא את השיבוץ לקובץ Excel.
""")

# קלט מהמשתמש
num_interns = st.slider("כמה מתמחים לשבץ?", min_value=5, max_value=30, value=10)
run_button = st.button("▶ הרץ שיבוץ")

if run_button:
    NUM_DAYS = 30
    SHIFT_TYPES = ['regular_weekday', 'night_weekday', 'regular_friday', 'night_friday', 'night_saturday']
    # שעות מוכפלות פי 2 כדי לעבוד עם מספרים שלמים בלבד
    SHIFT_HOURS = {'regular_weekday': 16, 'night_weekday': 32,
                   'regular_friday': 10, 'night_friday': 38, 'night_saturday': 48}
    WEEKEND_SHIFTS = ['night_friday', 'night_saturday']

    model = cp_model.CpModel()
    intern_assigned = {}
    for i in range(num_interns):
        for d in range(NUM_DAYS):
            for s in SHIFT_TYPES:
                intern_assigned[(i, d, s)] = model.NewBoolVar(f"intern_{i}_day_{d}_{s}")

    for d in range(NUM_DAYS):
        for s in SHIFT_TYPES:
            model.AddExactlyOne(intern_assigned[(i, d, s)] for i in range(num_interns))

    for i in range(num_interns):
        for week in range(4):
            start_day = week * 7
            end_day = min(start_day + 7, NUM_DAYS)
            total_hours = []
            for d in range(start_day, end_day):
                for s in SHIFT_TYPES:
                    total_hours.append(intern_assigned[(i, d, s)] * SHIFT_HOURS[s])
            model.Add(cp_model.LinearExpr.Sum(total_hours) <= 143)  # במקום 71.5

    for i in range(num_interns):
        for week in range(4):
            start_day = week * 7
            end_day = min(start_day + 7, NUM_DAYS)
            night_shifts = []
            for d in range(start_day, end_day):
                for s in ['night_weekday', 'night_friday', 'night_saturday']:
                    night_shifts.append(intern_assigned[(i, d, s)])
            model.Add(cp_model.LinearExpr.Sum(night_shifts) <= 2)

    for i in range(num_interns):
        weekend_shifts = [intern_assigned[(i, d, s)] for d in range(NUM_DAYS) for s in WEEKEND_SHIFTS]
        model.Add(cp_model.LinearExpr.Sum(weekend_shifts) <= 1)

    for i in range(num_interns):
        for d in range(NUM_DAYS - 2):
            current_night = [intern_assigned[(i, d, s)] for s in ['night_weekday', 'night_friday', 'night_saturday']]
            next_48h = [intern_assigned[(i, d2, s)] for d2 in [d+1, d+2] if d2 < NUM_DAYS for s in ['night_weekday', 'night_friday', 'night_saturday']]
            for c in current_night:
                for n in next_48h:
                    model.Add(c + n <= 1)

    total_hours_per_intern = []
    for i in range(num_interns):
        total_hours = []
        for d in range(NUM_DAYS):
            for s in SHIFT_TYPES:
                total_hours.append(intern_assigned[(i, d, s)] * SHIFT_HOURS[s])
        total_hours_per_intern.append(cp_model.LinearExpr.Sum(total_hours))

    max_diff = model.NewIntVar(0, 1000, 'max_diff')
    for i in range(num_interns):
        for j in range(i + 1, num_interns):
            diff = model.NewIntVar(-1000, 1000, f'diff_{i}_{j}')
            model.Add(diff == total_hours_per_intern[i] - total_hours_per_intern[j])
            model.AddAbsEquality(model.NewIntVar(0, 1000, ''), diff)
            model.AddAbsEquality(max_diff, diff).OnlyEnforceIf(model.NewBoolVar(f'enf_{i}_{j}'))

    model.Minimize(max_diff)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        rows = []
        for d in range(NUM_DAYS):
            for s in SHIFT_TYPES:
                for i in range(num_interns):
                    if solver.Value(intern_assigned[(i, d, s)]):
                        rows.append({'יום': d + 1, 'משמרת': s, 'מתמחה': i})
        schedule_df = pd.DataFrame(rows)
        st.success("השיבוץ נוצר בהצלחה!")
        st.dataframe(schedule_df)

        # הורדה לאקסל
        excel_file = schedule_df.to_excel(index=False)
        st.download_button(
            label="📥 הורד את השיבוץ לקובץ Excel",
            data=excel_file,
            file_name="shifts_schedule.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("❌ לא נמצא פתרון לשיבוץ. נסה עם מספר שונה של מתמחים.")
