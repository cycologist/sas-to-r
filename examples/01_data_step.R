# Converted from 01_data_step.sas by sas_to_r.py
# R output; review warnings and generated code before use.

# ---- data step: work.students ----
students <- read.table(
  text = "1 Alice 20 88\n2 Bob 22 91\n3 Carol 21 79\n4 David 23 95\n5 Eve 20 84",
  header = FALSE,
  stringsAsFactors = FALSE,
  comment.char = "",
  colClasses = c("numeric", "character", "numeric", "numeric")
)
names(students) <- c("id", "name", "age", "score")

# ---- data step: work.students_clean ----
students_clean <- students
students_clean <- students_clean[which(students_clean$age >= 21), , drop = FALSE]
students_clean$total <- students_clean$score + 5
students_clean$grade <- ifelse(students_clean$score >= 90, "A", "B")
attr(students_clean$total, "label") <- "Adjusted score"
students_clean <- students_clean[, c("id", "name", "age", "score", "total", "grade"), drop = FALSE]
