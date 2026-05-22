
# Import


In this part of the book, you’ll learn how to import a wider range of data into R, as well as how to get it into a form useful for analysis. Sometimes this is just a matter of calling a function from the appropriate data import package. But in more complex cases it might require both tidying and transformation in order to get to the tidy rectangle that you’d prefer to work with.


In this part of the book you’ll learn how to access data stored in the following ways:

- In20  Spreadsheets, you’ll learn how to import data from Excel spreadsheets and Google Sheets.

In20  Spreadsheets, you’ll learn how to import data from Excel spreadsheets and Google Sheets.

- In21  Databases, you’ll learn about getting data out of a database and into R (and you’ll also learn a little about how to get data out of R and into a database).

In21  Databases, you’ll learn about getting data out of a database and into R (and you’ll also learn a little about how to get data out of R and into a database).

- In22  Arrow, you’ll learn about Arrow, a powerful tool for working with out-of-memory data, particularly when it’s stored in the parquet format.

In22  Arrow, you’ll learn about Arrow, a powerful tool for working with out-of-memory data, particularly when it’s stored in the parquet format.

- In23  Hierarchical data, you’ll learn how to work with hierarchical data, including the deeply nested lists produced by data stored in the JSON format.

In23  Hierarchical data, you’ll learn how to work with hierarchical data, including the deeply nested lists produced by data stored in the JSON format.

- In24  Web scraping, you’ll learn web “scraping”, the art and science of extracting data from web pages.

In24  Web scraping, you’ll learn web “scraping”, the art and science of extracting data from web pages.


There are two important tidyverse packages that we don’t discuss here: haven and xml2. If you’re working with data from SPSS, Stata, and SAS files, check out thehavenpackage,https://haven.tidyverse.org. If you’re working with XML data, check out thexml2package,https://xml2.r-lib.org. Otherwise, you’ll need to do some research to figure out which package you’ll need to use; google is your friend here 😃.
