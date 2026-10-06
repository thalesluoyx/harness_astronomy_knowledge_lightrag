# POC requirement

## POC任务
根据ADR-01-Knowledge-Base-Selection.md 和 ADR-02-Knowledge-Base-Selection-Review.md  执行天文学知识库 POC。

## POC 语料
语料选取下面的"*_bilingual.md",这是一套"The Deep Sky Companions"丛书：
bilingual_output\book_Hidden Treasures (2007)
bilingual_output\book_Southern Gems (2013)
bilingual_output\book_The Caldwell Objects (2003)
bilingual_output\book_The Messier Objects (1998)
bilingual_output\book_The Secret Deep (2011)

## POC 要求
根据[python-standard-layout](slashCommand;python-standard-layout) 提供的标准python项目结构。
根据[python-testing-standard](slashCommand;python-testing-standard) 提供的测试标准，编写相应的测试用例。

建立harness的知识库更新机制，要求：
- 先建立整套lightrag知识库的框架
- 我把新的书籍放到指定的目录，然后运行harness，自动更新知识库。






