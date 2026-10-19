/* Example 1: create a small dataset with DATALINES, then clean it. */
data work.students;
    input id name $ age score;
    datalines;
1 Alice 20 88
2 Bob 22 91
3 Carol 21 79
4 David 23 95
5 Eve 20 84
;
run;

data work.students_clean;
    set work.students;

    /* Keep students who are at least 21. */
    if age >= 21;

    total = score + 5;

    if score >= 90 then grade = "A";
    else grade = "B";

    label total = "Adjusted score";
    keep id name age score total grade;
run;
