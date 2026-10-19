/* Example 2: common reporting procedures on an employee dataset. */
data work.employees;
    input emp_id name $ dept $ salary;
    datalines;
101 Alice Sales 62000
102 Bob Sales 58000
103 Carol IT 71000
104 David IT 68000
105 Eve HR 54000
106 Frank Sales 61000
;
run;

proc sort data=work.employees out=work.employees_by_salary;
    by descending salary;
run;

proc print data=work.employees_by_salary;
    var emp_id name dept salary;
run;

proc means data=work.employees;
    var salary;
    class dept;
run;

proc freq data=work.employees;
    tables dept;
run;
