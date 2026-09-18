-- Bracket-heavy multi-table T-SQL: the case tree-sitter-sql CANNOT segment.
--
-- The grammar has no concept of [bracket] quoting, so it recovers via ERROR
-- nodes; once NOT NULL appears (ubiquitous in real schemas) the recovery
-- swallows the FOLLOWING statement into the preceding create_table node. That
-- costs the swallowed table its symbol, mis-attributes its columns, and turns
-- its FK into a confident SELF edge on the wrong table. Milestone 4 therefore
-- segments CREATE TABLE by regex and lets the grammar keep only the tables it
-- parsed 1:1. This fixture pins that repair, plus the two phantom-table guards
-- (commented-out DDL and dynamic SQL) that regex segmentation makes necessary.

-- Ends on a bracketed NOT NULL column, which is what makes the grammar swallow
-- the NEXT statement into this create_table node. [Name] is also the keyword
-- collision that makes the grammar drop a column outright.
CREATE TABLE [dbo].[Customer] (
    [CustomerId] INT NOT NULL PRIMARY KEY,
    [Region] NVARCHAR(50) NULL,
    [Name] NVARCHAR(100) NOT NULL
);
GO

CREATE TABLE [dbo].[Orders] (
    [OrderId] INT NOT NULL PRIMARY KEY,
    [CustomerId] INT NOT NULL,
    [Total] DECIMAL(18,2) NULL,
    CONSTRAINT [FK_Orders_Customer] FOREIGN KEY ([CustomerId]) REFERENCES [dbo].[Customer]([CustomerId])
);
GO

CREATE TABLE [dbo].[OrderLine] (
    [OrderLineId] INT NOT NULL PRIMARY KEY,
    [OrderId] INT NOT NULL,
    [Qty] DECIMAL(9,3) NOT NULL,
    FOREIGN KEY ([OrderId]) REFERENCES [dbo].[Orders]([OrderId])
);
GO

-- Transient staging table: bracketed columns + NOT NULL, inside the merge zone.
CREATE TABLE #OrderStaging (
    [OrderId] INT NOT NULL,
    [Payload] NVARCHAR(MAX) NULL
);
GO

-- Commented-out DDL must NOT become a table:
-- CREATE TABLE [dbo].[GhostFromComment] ([Id] INT NOT NULL);
/* CREATE TABLE [dbo].[GhostFromBlockComment] ([Id] INT NOT NULL); */

-- Dynamic SQL must NOT become a table either.
EXEC('CREATE TABLE [dbo].[GhostFromDynamicSql] ([Id] INT NOT NULL)');
GO

CREATE PROCEDURE [dbo].[usp_GetOrders]
AS
BEGIN
    SELECT o.[OrderId], c.[Name]
    FROM [dbo].[Orders] o
    JOIN [dbo].[Customer] c ON c.[CustomerId] = o.[CustomerId];
END;
