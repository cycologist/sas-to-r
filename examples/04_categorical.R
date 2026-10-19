# Converted from 04_categorical.sas by sas_to_r.py
# R output; review warnings and generated code before use.

# ---- data step: work.customers ----
customers <- read.table(
  text = "1 25 32000 Basic 0\n2 31 41000 Basic 0\n3 47 62000 Basic 1\n4 52 71000 Basic 1\n5 23 28000 Basic 0\n6 38 52000 Basic 0\n7 29 36000 Basic 1\n8 35 45000 Basic 0\n9 44 58000 Basic 1\n10 56 76000 Basic 1\n11 27 33000 Basic 0\n12 39 50000 Basic 0\n13 33 47000 Premium 1\n14 41 64000 Premium 1\n15 50 82000 Premium 0\n16 58 91000 Premium 1\n17 36 55000 Premium 0\n18 45 69000 Premium 1\n19 28 38000 Premium 1\n20 40 60000 Premium 0\n21 48 72000 Premium 1\n22 54 85000 Premium 1\n23 32 44000 Premium 0\n24 37 53000 Premium 1",
  header = FALSE,
  stringsAsFactors = FALSE,
  comment.char = "",
  colClasses = c("numeric", "numeric", "numeric", "character", "numeric")
)
names(customers) <- c("id", "age", "income", "group", "churn")

# ---- proc freq: customers ----
freq_table_1 <- table(customers$group, customers$churn)
print(freq_table_1)
print(round(prop.table(freq_table_1, 1), 3))
print(round(outer(rowSums(freq_table_1), colSums(freq_table_1)) / sum(freq_table_1), 3))
print(chisq.test(freq_table_1, correct = FALSE))

# ---- proc logistic: customers ----
logit_fit_1 <- stats::glm(I(churn == "1") ~ age + income + factor(group), data = customers, family = stats::binomial())
print(summary(logit_fit_1))
logit_fit_1_coef <- stats::coef(logit_fit_1)
logit_fit_1_se <- sqrt(diag(stats::vcov(logit_fit_1)))
print(exp(cbind(OR = logit_fit_1_coef, `2.5 %` = logit_fit_1_coef - 1.96 * logit_fit_1_se, `97.5 %` = logit_fit_1_coef + 1.96 * logit_fit_1_se)))
