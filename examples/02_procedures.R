# Converted from 02_procedures.sas by sas_to_r.py
# R output; review warnings and generated code before use.

.sas_summary <- function(x) {
  values <- x[!is.na(x)]
  n <- length(values)
  c(
    n = n,
    mean = if (n > 0) mean(values) else NA_real_,
    sd = if (n > 1) sd(values) else NA_real_,
    min = if (n > 0) min(values) else NA_real_,
    max = if (n > 0) max(values) else NA_real_
  )
}

# ---- data step: work.employees ----
employees <- read.table(
  text = "101 Alice Sales 62000\n102 Bob Sales 58000\n103 Carol IT 71000\n104 David IT 68000\n105 Eve HR 54000\n106 Frank Sales 61000",
  header = FALSE,
  stringsAsFactors = FALSE,
  comment.char = "",
  colClasses = c("numeric", "character", "character", "numeric")
)
names(employees) <- c("emp_id", "name", "dept", "salary")

# ---- proc sort: employees -> employees_by_salary ----
employees_by_salary <- employees[order(-xtfrm(employees$salary)), , drop = FALSE]

# ---- proc print: employees_by_salary ----
print(employees_by_salary[, c("emp_id", "name", "dept", "salary"), drop = FALSE])

# ---- proc means: employees ----
print(aggregate(cbind(salary) ~ dept, data = employees, FUN = .sas_summary, na.action = na.pass))

# ---- proc freq: employees ----
freq_table_1 <- table(employees$dept)
print(freq_table_1)
