---
name: shift-and-study
description: Plans a working student's week around their campus job shifts, class times and Canvas deadlines, and warns before crunch days. Use when the student mentions work, a shift, Workday, being too busy, falling behind on lectures, or fitting in studying around a job.
---

# Shift and Study

For students who work on campus and also take classes. It reads their work shifts, class times and Canvas, fits the study tasks into the gaps, and warns about days where work and a deadline collide.
It differs from the built-in study-plan-builder: it knows the student's work shifts, catches up on newly posted lectures, and sends a heads-up before a crunch day.

## When to use

- "i work tuesday and thursday nights and have a lab due thursday, help"
- "what do i need to do this week around my shifts"
- "i fell behind on lectures, what did i miss"
- "when can i actually study this week"

Do not use it for exam-only prep or for anything that changes Workday or Canvas.

## Step 1: Work shifts (once, then reuse)

Check memory for saved shifts first. If there are none, offer these in order and use the first the student likes:

1. The student types them: "Tue 4-9pm library desk, Thu 4-9pm". Easiest.
2. The student sends a screenshot or photo of their Workday schedule. Read it and confirm the shifts back.
3. Cubbie's browser opens the school's Workday site, with the student signing in and taking over for SSO or two-factor codes. Read the schedule only. Ask which site to open if you do not know it.

Save the shifts with:

python3 scripts/balance.py shifts --set "Tue 16:00-21:00 Library desk; Thu 16:00-21:00 Library desk"

Remember in memory that shifts are saved. Never clock in, submit a timesheet, swap or drop a shift. If shifts change, set them again.

## Step 2: Gather the week

1. Read the student's Canvas upcoming assignments and quizzes for the next 7 days, and their class meeting times from Canvas or Google Calendar.
   If Canvas is not connected, ask them to connect it. If they would rather not, ask what is due this week and continue.
2. Read what was newly posted in Canvas in the last 7 days (lecture recordings, slides, modules, announcements). Each unwatched lecture becomes a catch-up task with kind "lecture", due at the next class meeting.
3. Estimate hours for each task: assignment 2, lab or report 3, project 4, quiz 1, a lecture 1 (or its length if Canvas says). Say these are guesses and ask the student to correct any that are off. Remember corrections in memory.
4. Write one JSON file in the HOME folder, as in assets/sample_input.json. Use the student's local date and the dated classes in "busy". Leave "shifts" out to use the saved ones.

## Step 3: Plan

Run from this Skill's folder, with the student's local time:

python3 scripts/balance.py plan --input ~/week.json --now HH:MM

To try it without any input, use plan --sample instead. Read the output, then:

- Tell the student the first study block today and any crunch day. Do not paste the whole plan.
- Anything under "Could not fit": say how many hours are short and suggest options (ask for an extension from the professor, move a study block, or ask a classmate for notes). Offer to draft an email to the professor and wait for a yes before anything is sent. Never write or do the graded work.
- If the plan is longer than five lines, make a one-page PDF and send it.

## Step 4: Offer check-ins, only after a yes

Ask one at a time. Create nothing until the student agrees:

- A Sunday check-in at a time they choose (suggest 6 pm) that builds the coming week. Word it so it makes sense later: "Shift and Study: read the student's Canvas due dates and new lectures for the next 7 days and run the plan."
- A heads-up the evening before any crunch day, saying what is due and when the first free block is.
- Calendar blocks for the study sessions, after showing exactly what will be added.

## Replies

Short plain text, no Markdown, one idea per message. Lead with what matters today. Links on their own line. Example:

Heavy day Thursday: 5h shift, then Lab 4 due at 11:59.
Best window: Wed 5-8 pm.

Want a heads-up Wednesday night?

## When something fails

| Situation | What to do |
| --- | --- |
| Canvas not connected | Ask them to connect it, or ask what is due this week |
| No shifts saved and the student does not want to share | Plan around classes only and say so |
| Workday needs a sign-in | Hand the browser to the student; never ask for a password in chat |
| balance.py exit 2 | A time, date or shift was malformed; fix the input and run once more |
| balance.py exit 3 | Nothing to plan; say the week looks clear and offer to look further ahead |
| Nothing new posted in Canvas | Skip the lecture catch-up and say so |

Use only dates and times that Canvas, the calendar or the student gave you. Never guess a due date or a shift.