var today = new Date();

/*Data transfered today*/
barChart("#plot_data_today", 800, 300, "Transferred data", "Time", "Data [MB]",
         "/rest/statistics/data_per_day",
         '{"day": today.getDate(), "month": today.getMonth()+1, "year": today.getFullYear()}');

/*Number files transfered today*/
barChart("#plot_number_files_today", 800, 300, "Transferred files", "Time", "Number",
         "/rest/statistics/number_files_per_day",
         '{"day": today.getDate(), "month": today.getMonth()+1, "year": today.getFullYear()}');
