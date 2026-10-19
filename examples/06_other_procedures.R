# Converted from 06_other_procedures.sas by sas_to_r.py
# R output; review warnings and generated code before use.

# ---- data step: work.scores ----
scores <- read.table(
  text = "1 A M 78 70 72 2\n2 A F 82 75 79 3\n3 A M 75 68 71 2\n4 A F 88 80 85 4\n5 A M 80 73 77 3\n6 A F 85 78 80 4\n7 B F 90 84 87 5\n8 B M 92 86 91 6\n9 B F 87 81 85 4\n10 B M 94 88 90 6\n11 B F 89 83 86 5\n12 B M 91 85 90 6\n13 C M 98 92 96 7\n14 C F 95 89 91 6\n15 C M 99 93 96 8\n16 C F 96 90 95 7\n17 C M 97 91 95 7\n18 C F 100 94 96 8",
  header = FALSE,
  stringsAsFactors = FALSE,
  comment.char = "",
  colClasses = c("numeric", "character", "character", "numeric", "numeric", "numeric", "numeric")
)
names(scores) <- c("id", "group", "sex", "score", "before", "after", "count")

# ---- proc ttest: scores ----
if (nlevels(factor(scores$sex)) == 2L) {
  print(stats::t.test(score ~ factor(sex), data = scores, mu = 0, alternative = "two.sided"))
} else {
  print(stats::pairwise.t.test(scores$score, factor(scores$sex), p.adjust.method = "none"))
}
print(stats::t.test(scores$before, scores$after, paired = TRUE, mu = 0, alternative = "two.sided"))

# ---- proc npar1way: scores ----
if (nlevels(factor(scores$group)) == 2L) {
  print(stats::wilcox.test(score ~ factor(group), data = scores))
} else {
  print(stats::kruskal.test(score ~ factor(group), data = scores))
}

# ---- proc anova: scores ----
glm_fit_1 <- stats::lm(score ~ factor(group), data = scores)
print(summary(glm_fit_1))
print(stats::anova(glm_fit_1))
print(stats::aggregate(score ~ group, data = scores, FUN = mean, na.rm = TRUE))

# ---- proc genmod: scores ----
genmod_fit_1 <- stats::glm(count ~ factor(group) + score, data = scores, family = stats::poisson(link = "log"))
print(summary(genmod_fit_1))
print(stats::anova(genmod_fit_1))
