- Program
- 27A field guide to base R

# 27A field guide to base R


## 27.1Introduction


To finish off the programming section, we’re going to give you a quick tour of the most important base R functions that we don’t otherwise discuss in the book. These tools are particularly useful as you do more programming and will help you read code you’ll encounter in the wild.


This is a good place to remind you that the tidyverse is not the only way to solve data science problems. We teach the tidyverse in this book because tidyverse packages share a common design philosophy, increasing the consistency across functions, and making each new function or package a little easier to learn and use. It’s not possible to use the tidyverse without using base R, so we’ve actually already taught you alotof base R functions: fromlibrary()to load packages, tosum()andmean()for numeric summaries, to the factor, date, and POSIXct data types, and of course all the basic operators like+,-,/,*,|,&, and!. What we haven’t focused on so far is base R workflows, so we will highlight a few of those in this chapter.


After you read this book, you’ll learn other approaches to the same problems using base R, data.table, and other packages. You’ll undoubtedly encounter these other approaches when you start reading R code written by others, particularly if you’re using Stack Overflow. It’s 100% okay to write code that uses a mix of approaches, and don’t let anyone tell you otherwise!


In this chapter, we’ll focus on four big topics: subsetting with[, subsetting with[[and$, the apply family of functions, andforloops. To finish off, we’ll briefly discuss two essential plotting functions.


### 27.1.1Prerequisites


This package focuses on base R so doesn’t have any real prerequisites, but we’ll load the tidyverse in order to explain some of the differences.


```
library(tidyverse)
```


## 27.2Selecting multiple elements with[


[is used to extract sub-components from vectors and data frames, and is called likex[i]orx[i, j]. In this section, we’ll introduce you to the power of[, first showing you how you can use it with vectors, then how the same principles extend in a straightforward way to two-dimensional (2d) structures like data frames. We’ll then help you cement that knowledge by showing how various dplyr verbs are special cases of[.


### 27.2.1Subsetting vectors


There are five main types of things that you can subset a vector with, i.e., that can be theiinx[i]:

- A vector of positive integers. Subsetting with positive integers keeps the elements at those positions:x<-c("one","two","three","four","five")x[c(3,2,5)]#> [1] "three" "two"   "five"By repeating a position, you can actually make a longer output than input, making the term “subsetting” a bit of a misnomer.x[c(1,1,5,5,5,2)]#> [1] "one"  "one"  "five" "five" "five" "two"

A vector of positive integers. Subsetting with positive integers keeps the elements at those positions:


```
x <- c("one", "two", "three", "four", "five")
x[c(3, 2, 5)]
#> [1] "three" "two"   "five"
```


By repeating a position, you can actually make a longer output than input, making the term “subsetting” a bit of a misnomer.


```
x[c(1, 1, 5, 5, 5, 2)]
#> [1] "one"  "one"  "five" "five" "five" "two"
```

- A vector of negative integers. Negative values drop the elements at the specified positions:x[c(-1,-3,-5)]#> [1] "two"  "four"

A vector of negative integers. Negative values drop the elements at the specified positions:


```
x[c(-1, -3, -5)]
#> [1] "two"  "four"
```

- A logical vector. Subsetting with a logical vector keeps all values corresponding to aTRUEvalue. This is most often useful in conjunction with the comparison functions.x<-c(10,3,NA,5,8,1,NA)# All non-missing values of xx[!is.na(x)]#> [1] 10  3  5  8  1# All even (or missing!) values of xx[x%%2==0]#> [1] 10 NA  8 NAUnlikefilter(),NAindices will be included in the output asNAs.

A logical vector. Subsetting with a logical vector keeps all values corresponding to aTRUEvalue. This is most often useful in conjunction with the comparison functions.


```
x <- c(10, 3, NA, 5, 8, 1, NA)

# All non-missing values of x
x[!is.na(x)]
#> [1] 10  3  5  8  1

# All even (or missing!) values of x
x[x %% 2 == 0]
#> [1] 10 NA  8 NA
```


Unlikefilter(),NAindices will be included in the output asNAs.

- A character vector. If you have a named vector, you can subset it with a character vector:x<-c(abc=1, def=2, xyz=5)x[c("xyz","def")]#> xyz def#>   5   2As with subsetting with positive integers, you can use a character vector to duplicate individual entries.

A character vector. If you have a named vector, you can subset it with a character vector:


```
x <- c(abc = 1, def = 2, xyz = 5)
x[c("xyz", "def")]
#> xyz def 
#>   5   2
```


As with subsetting with positive integers, you can use a character vector to duplicate individual entries.

- Nothing. The final type of subsetting is nothing,x[], which returns the completex. This is not useful for subsetting vectors, but as we’ll see shortly, it is useful when subsetting 2d structures like tibbles.

Nothing. The final type of subsetting is nothing,x[], which returns the completex. This is not useful for subsetting vectors, but as we’ll see shortly, it is useful when subsetting 2d structures like tibbles.


### 27.2.2Subsetting data frames


There are quite a few different ways1that you can use[with a data frame, but the most important way is to select rows and columns independently withdf[rows, cols]. Hererowsandcolsare vectors as described above. For example,df[rows, ]anddf[, cols]select just rows or just columns, using the empty subset to preserve the other dimension.


Here are a couple of examples:


```
df <- tibble(
  x = 1:3, 
  y = c("a", "e", "f"), 
  z = runif(3)
)

# Select first row and second column
df[1, 2]
#> # A tibble: 1 × 1
#>   y    
#>   <chr>
#> 1 a

# Select all rows and columns x and y
df[, c("x" , "y")]
#> # A tibble: 3 × 2
#>       x y    
#>   <int> <chr>
#> 1     1 a    
#> 2     2 e    
#> 3     3 f

# Select rows where `x` is greater than 1 and all columns
df[df$x > 1, ]
#> # A tibble: 2 × 3
#>       x y         z
#>   <int> <chr> <dbl>
#> 1     2 e     0.834
#> 2     3 f     0.601
```


We’ll come back to$shortly, but you should be able to guess whatdf$xdoes from the context: it extracts thexvariable fromdf. We need to use it here because[doesn’t use tidy evaluation, so you need to be explicit about the source of thexvariable.


There’s an important difference between tibbles and data frames when it comes to[. In this book, we’ve mainly used tibbles, whicharedata frames, but they tweak some behaviors to make your life a little easier. In most places, you can use “tibble” and “data frame” interchangeably, so when we want to draw particular attention to R’s built-in data frame, we’ll writedata.frame. Ifdfis adata.frame, thendf[, cols]will return a vector ifcolsselects a single column and a data frame if it selects more than one column. Ifdfis a tibble, then[will always return a tibble.


```
df1 <- data.frame(x = 1:3)
df1[, "x"]
#> [1] 1 2 3

df2 <- tibble(x = 1:3)
df2[, "x"]
#> # A tibble: 3 × 1
#>       x
#>   <int>
#> 1     1
#> 2     2
#> 3     3
```


One way to avoid this ambiguity withdata.frames is to explicitly specifydrop = FALSE:


```
df1[, "x" , drop = FALSE]
#>   x
#> 1 1
#> 2 2
#> 3 3
```


### 27.2.3dplyr equivalents


Several dplyr verbs are special cases of[:

- filter()is equivalent to subsetting the rows with a logical vector, taking care to exclude missing values:df<-tibble(x=c(2,3,1,1,NA),y=letters[1:5],z=runif(5))df|>filter(x>1)# same asdf[!is.na(df$x)&df$x>1,]Another common technique in the wild is to usewhich()for its side-effect of dropping missing values:df[which(df$x > 1), ].

filter()is equivalent to subsetting the rows with a logical vector, taking care to exclude missing values:


```
df <- tibble(
  x = c(2, 3, 1, 1, NA), 
  y = letters[1:5], 
  z = runif(5)
)
df |> filter(x > 1)

# same as
df[!is.na(df$x) & df$x > 1, ]
```


Another common technique in the wild is to usewhich()for its side-effect of dropping missing values:df[which(df$x > 1), ].

- arrange()is equivalent to subsetting the rows with an integer vector, usually created withorder():df|>arrange(x,y)# same asdf[order(df$x,df$y),]You can useorder(decreasing = TRUE)to sort all columns in descending order or-rank(col)to sort columns in decreasing order individually.

arrange()is equivalent to subsetting the rows with an integer vector, usually created withorder():


```
df |> arrange(x, y)

# same as
df[order(df$x, df$y), ]
```


You can useorder(decreasing = TRUE)to sort all columns in descending order or-rank(col)to sort columns in decreasing order individually.

- Bothselect()andrelocate()are similar to subsetting the columns with a character vector:df|>select(x,z)# same asdf[,c("x","z")]

Bothselect()andrelocate()are similar to subsetting the columns with a character vector:


```
df |> select(x, z)

# same as
df[, c("x", "z")]
```


Base R also provides a function that combines the features offilter()andselect()2calledsubset():


```
df |> 
  filter(x > 1) |> 
  select(y, z)
#> # A tibble: 2 × 2
#>   y           z
#>   <chr>   <dbl>
#> 1 a     0.157  
#> 2 b     0.00740
```


```
# same as
df |> subset(x > 1, c(y, z))
```


This function was the inspiration for much of dplyr’s syntax.


### 27.2.4Exercises

- Create functions that take a vector as input and return:The elements at even-numbered positions.Every element except the last value.Only even values (and no missing values).

Create functions that take a vector as input and return:

- The elements at even-numbered positions.
- Every element except the last value.
- Only even values (and no missing values).
- Why isx[-which(x > 0)]not the same asx[x <= 0]? Read the documentation forwhich()and do some experiments to figure it out.

Why isx[-which(x > 0)]not the same asx[x <= 0]? Read the documentation forwhich()and do some experiments to figure it out.


## 27.3Selecting a single element with$and[[


[, which selects many elements, is paired with[[and$, which extract a single element. In this section, we’ll show you how to use[[and$to pull columns out of data frames, discuss a couple more differences betweendata.framesand tibbles, and emphasize some important differences between[and[[when used with lists.


### 27.3.1Data frames


[[and$can be used to extract columns out of a data frame.[[can access by position or by name, and$is specialized for access by name:


```
tb <- tibble(
  x = 1:4,
  y = c(10, 4, 1, 21)
)

# by position
tb[[1]]
#> [1] 1 2 3 4

# by name
tb[["x"]]
#> [1] 1 2 3 4
tb$x
#> [1] 1 2 3 4
```


They can also be used to create new columns, the base R equivalent ofmutate():


```
tb$z <- tb$x + tb$y
tb
#> # A tibble: 4 × 3
#>       x     y     z
#>   <int> <dbl> <dbl>
#> 1     1    10    11
#> 2     2     4     6
#> 3     3     1     4
#> 4     4    21    25
```


There are several other base R approaches to creating new columns including withtransform(),with(), andwithin(). Hadley collected a few examples athttps://gist.github.com/hadley/1986a273e384fb2d4d752c18ed71bedf.


Using$directly is convenient when performing quick summaries. For example, if you just want to find the size of the biggest diamond or the possible values ofcut, there’s no need to usesummarize():


```
max(diamonds$carat)
#> [1] 5.01

levels(diamonds$cut)
#> [1] "Fair"      "Good"      "Very Good" "Premium"   "Ideal"
```


dplyr also provides an equivalent to[[/$that we didn’t mention inChapter 3:pull().pull()takes either a variable name or variable position and returns just that column. That means we could rewrite the above code to use the pipe:


```
diamonds |> pull(carat) |> max()
#> [1] 5.01

diamonds |> pull(cut) |> levels()
#> [1] "Fair"      "Good"      "Very Good" "Premium"   "Ideal"
```


### 27.3.2Tibbles


There are a couple of important differences between tibbles and basedata.frames when it comes to$. Data frames match the prefix of any variable names (so-calledpartial matching) and don’t complain if a column doesn’t exist:


```
df <- data.frame(x1 = 1)
df$x
#> [1] 1
df$z
#> NULL
```


Tibbles are more strict: they only ever match variable names exactly and they will generate a warning if the column you are trying to access doesn’t exist:


```
tb <- tibble(x1 = 1)

tb$x
#> Warning: Unknown or uninitialised column: `x`.
#> NULL
tb$z
#> Warning: Unknown or uninitialised column: `z`.
#> NULL
```


For this reason we sometimes joke that tibbles are lazy and surly: they do less and complain more.


### 27.3.3Lists


[[and$are also really important for working with lists, and it’s important to understand how they differ from[. Let’s illustrate the differences with a list namedl:


```
l <- list(
  a = 1:3, 
  b = "a string", 
  c = pi, 
  d = list(-1, -5)
)
```

- [extracts a sub-list. It doesn’t matter how many elements you extract, the result will always be a list.str(l[1:2])#> List of 2#>  $ a: int [1:3] 1 2 3#>  $ b: chr "a string"str(l[1])#> List of 1#>  $ a: int [1:3] 1 2 3str(l[4])#> List of 1#>  $ d:List of 2#>   ..$ : num -1#>   ..$ : num -5Like with vectors, you can subset with a logical, integer, or character vector.

[extracts a sub-list. It doesn’t matter how many elements you extract, the result will always be a list.


```
str(l[1:2])
#> List of 2
#>  $ a: int [1:3] 1 2 3
#>  $ b: chr "a string"

str(l[1])
#> List of 1
#>  $ a: int [1:3] 1 2 3

str(l[4])
#> List of 1
#>  $ d:List of 2
#>   ..$ : num -1
#>   ..$ : num -5
```


Like with vectors, you can subset with a logical, integer, or character vector.

- [[and$extract a single component from a list. They remove a level of hierarchy from the list.str(l[[1]])#>  int [1:3] 1 2 3str(l[[4]])#> List of 2#>  $ : num -1#>  $ : num -5str(l$a)#>  int [1:3] 1 2 3

[[and$extract a single component from a list. They remove a level of hierarchy from the list.


```
str(l[[1]])
#>  int [1:3] 1 2 3

str(l[[4]])
#> List of 2
#>  $ : num -1
#>  $ : num -5

str(l$a)
#>  int [1:3] 1 2 3
```


The difference between[and[[is particularly important for lists because[[drills down into the list while[returns a new, smaller list. To help you remember the difference, take a look at the unusual pepper shaker shown inFigure27.1. If this pepper shaker is your listpepper, then,pepper[1]is a pepper shaker containing a single pepper packet.pepper[2]would look the same, but would contain the second packet.pepper[1:2]would be a pepper shaker containing two pepper packets.pepper[[1]]would extract the pepper packet itself.


This same principle applies when you use 1d[with a data frame:df["x"]returns a one-column data frame anddf[["x"]]returns a vector.


### 27.3.4Exercises

- What happens when you use[[with a positive integer that’s bigger than the length of the vector? What happens when you subset with a name that doesn’t exist?

What happens when you use[[with a positive integer that’s bigger than the length of the vector? What happens when you subset with a name that doesn’t exist?

- What wouldpepper[[1]][1]be? What aboutpepper[[1]][[1]]?

What wouldpepper[[1]][1]be? What aboutpepper[[1]][[1]]?


## 27.4Apply family


InChapter 26, you learned tidyverse techniques for iteration likedplyr::across()and the map family of functions. In this section, you’ll learn about their base equivalents, theapply family. In this context apply and map are synonyms because another way of saying “map a function over each element of a vector” is “apply a function over each element of a vector”. Here we’ll give you a quick overview of this family so you can recognize them in the wild.


The most important member of this family islapply(), which is very similar topurrr::map()3. In fact, because we haven’t used any ofmap()’s more advanced features, you can replace everymap()call inChapter 26withlapply().


There’s no exact base R equivalent toacross()but you can get close by using[withlapply(). This works because under the hood, data frames are lists of columns, so callinglapply()on a data frame applies the function to each column.


```
df <- tibble(a = 1, b = 2, c = "a", d = "b", e = 4)

# First find numeric columns
num_cols <- sapply(df, is.numeric)
num_cols
#>     a     b     c     d     e 
#>  TRUE  TRUE FALSE FALSE  TRUE

# Then transform each column with lapply() then replace the original values
df[, num_cols] <- lapply(df[, num_cols, drop = FALSE], \(x) x * 2)
df
#> # A tibble: 1 × 5
#>       a     b c     d         e
#>   <dbl> <dbl> <chr> <chr> <dbl>
#> 1     2     4 a     b         8
```


The code above uses a new function,sapply(). It’s similar tolapply()but it always tries to simplify the result, hence thesin its name, here producing a logical vector instead of a list. We don’t recommend using it for programming, because the simplification can fail and give you an unexpected type, but it’s usually fine for interactive use. purrr has a similar function calledmap_vec()that we didn’t mention inChapter 26.


Base R provides a stricter version ofsapply()calledvapply(), short forvector apply. It takes an additional argument that specifies the expected type, ensuring that simplification occurs the same way regardless of the input. For example, we could replace thesapply()call above with thisvapply()where we specify that we expectis.numeric()to return a logical vector of length 1:


```
vapply(df, is.numeric, logical(1))
#>     a     b     c     d     e 
#>  TRUE  TRUE FALSE FALSE  TRUE
```


The distinction betweensapply()andvapply()is really important when they’re inside a function (because it makes a big difference to the function’s robustness to unusual inputs), but it doesn’t usually matter in data analysis.


Another important member of the apply family istapply()which computes a single grouped summary:


```
diamonds |> 
  group_by(cut) |> 
  summarize(price = mean(price))
#> # A tibble: 5 × 2
#>   cut       price
#>   <ord>     <dbl>
#> 1 Fair      4359.
#> 2 Good      3929.
#> 3 Very Good 3982.
#> 4 Premium   4584.
#> 5 Ideal     3458.

tapply(diamonds$price, diamonds$cut, mean)
#>      Fair      Good Very Good   Premium     Ideal 
#>  4358.758  3928.864  3981.760  4584.258  3457.542
```


Unfortunatelytapply()returns its results in a named vector which requires some gymnastics if you want to collect multiple summaries and grouping variables into a data frame (it’s certainly possible to not do this and just work with free floating vectors, but in our experience that just delays the work). If you want to see how you might usetapply()or other base techniques to perform other grouped summaries, Hadley has collected a few techniquesin a gist.


The final member of the apply family is the titularapply(), which works with matrices and arrays. In particular, watch out forapply(df, 2, something), which is a slow and potentially dangerous way of doinglapply(df, something). This rarely comes up in data science because we usually work with data frames and not matrices.


## 27.5forloops


forloops are the fundamental building block of iteration that both the apply and map families use under the hood.forloops are powerful and general tools that are important to learn as you become a more experienced R programmer. The basic structure of aforloop looks like this:


```
for (element in vector) {
  # do something with element
}
```


The most straightforward use offorloops is to achieve the same effect aswalk(): call some function with a side-effect on each element of a list. For example, inSection 26.4.1instead of usingwalk():


```
paths |> walk(append_file)
```


We could have used aforloop:


```
for (path in paths) {
  append_file(path)
}
```


Things get a little trickier if you want to save the output of theforloop, for example reading all of the excel files in a directory like we did inChapter 26:


```
paths <- dir("data/gapminder", pattern = "\\.xlsx$", full.names = TRUE)
files <- map(paths, readxl::read_excel)
```


There are a few different techniques that you can use, but we recommend being explicit about what the output is going to look like upfront. In this case, we’re going to want a list the same length aspaths, which we can create withvector():


```
files <- vector("list", length(paths))
```


Then instead of iterating over the elements ofpaths, we’ll iterate over their indices, usingseq_along()to generate one index for each element of paths:


```
seq_along(paths)
#>  [1]  1  2  3  4  5  6  7  8  9 10 11 12
```


Using the indices is important because it allows us to link to each position in the input with the corresponding position in the output:


```
for (i in seq_along(paths)) {
  files[[i]] <- readxl::read_excel(paths[[i]])
}
```


To combine the list of tibbles into a single tibble you can usedo.call()+rbind():


```
do.call(rbind, files)
#> # A tibble: 1,704 × 5
#>   country     continent lifeExp      pop gdpPercap
#>   <chr>       <chr>       <dbl>    <dbl>     <dbl>
#> 1 Afghanistan Asia         28.8  8425333      779.
#> 2 Albania     Europe       55.2  1282697     1601.
#> 3 Algeria     Africa       43.1  9279525     2449.
#> 4 Angola      Africa       30.0  4232095     3521.
#> 5 Argentina   Americas     62.5 17876956     5911.
#> 6 Australia   Oceania      69.1  8691212    10040.
#> # ℹ 1,698 more rows
```


Rather than making a list and saving the results as we go, a simpler approach is to build up the data frame piece-by-piece:


```
out <- NULL
for (path in paths) {
  out <- rbind(out, readxl::read_excel(path))
}
```


We recommend avoiding this pattern because it can become very slow when the vector is very long. This is the source of the persistent canard thatforloops are slow: they’re not, but iteratively growing a vector is.


## 27.6Plots


Many R users who don’t otherwise use the tidyverse prefer ggplot2 for plotting due to helpful features like sensible defaults, automatic legends, and a modern look. However, base R plotting functions can still be useful because they’re so concise — it takes very little typing to do a basic exploratory plot.


There are two main types of base plot you’ll see in the wild: scatterplots and histograms, produced withplot()andhist()respectively. Here’s a quick example from the diamonds dataset:


```
# Left
hist(diamonds$carat)

# Right
plot(diamonds$carat, diamonds$price)
```


Note that base plotting functions work with vectors, so you need to pull columns out of the data frame using$or some other technique.


## 27.7Summary


In this chapter, we’ve shown you a selection of base R functions useful for subsetting and iteration. Compared to approaches discussed elsewhere in the book, these functions tend to have more of a “vector” flavor than a “data frame” flavor because base R functions tend to take individual vectors, rather than a data frame and some column specification. This often makes life easier for programming and so becomes more important as you write more functions and begin to write your own packages.


This chapter concludes the programming section of the book. You’ve made a solid start on your journey to becoming not just a data scientist who uses R, but a data scientist who canprogramin R. We hope these chapters have sparked your interest in programming and that you’re looking forward to learning more outside of this book.

- Readhttps://adv-r.hadley.nz/subsetting.html#subset-multipleto see how you can also subset a data frame like it is a 1d object and how you can subset it with a matrix.↩︎

Readhttps://adv-r.hadley.nz/subsetting.html#subset-multipleto see how you can also subset a data frame like it is a 1d object and how you can subset it with a matrix.↩︎

- But it doesn’t handle grouped data frames differently and it doesn’t support selection helper functions likestarts_with().↩︎

But it doesn’t handle grouped data frames differently and it doesn’t support selection helper functions likestarts_with().↩︎

- It just lacks convenient features like progress bars and reporting which element caused the problem if there’s an error.↩︎

It just lacks convenient features like progress bars and reporting which element caused the problem if there’s an error.↩︎
