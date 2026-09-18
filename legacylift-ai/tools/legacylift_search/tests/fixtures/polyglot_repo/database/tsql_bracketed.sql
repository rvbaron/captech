-- SQL identifier normalization, transient-table classification, and CTE handling.
--
-- IMPORTANT tree-sitter-sql limitation: the grammar does not understand
-- [bracket] quoting and recovers via ERROR nodes. A bracketed CREATE TABLE that
-- also contains NOT NULL makes it MERGE the following table into the same node,
-- so a bracketed multi-table + FK schema cannot be segmented reliably. This
-- fixture therefore pins only what the grammar produces deterministically:
--   * cross-table FK resolution uses PLAIN table names with a bracketed/qualified
--     REFERENCES target (exercises ref-side normalization);
--   * a SINGLE bracketed/qualified table pins definition-side name normalization;
--   * transient objects and the CTE are each their own statement.

-- Cross-table FK: plain names segment reliably; the target is bracketed.
CREATE TABLE Customer (Id INT PRIMARY KEY, Name VARCHAR(100) NOT NULL);
CREATE TABLE Orders (OrderId INT PRIMARY KEY, CustomerId INT NOT NULL, FOREIGN KEY (CustomerId) REFERENCES [dbo].[Customer](Id));

-- Single bracketed/qualified table: symbol name must normalize to bare 'Widget'.
CREATE TABLE [dbo].[Widget] ([WidgetId] INT PRIMARY KEY, [Label] VARCHAR(50) NOT NULL);

-- Transient objects: T-SQL local temp (#), table variable (@), ANSI TEMPORARY.
CREATE TABLE #StagingRows (Id INT PRIMARY KEY);
CREATE TABLE @LineItems (Id INT);
CREATE TEMPORARY TABLE tmp_scratch (Id INT);

-- A CTE is not a durable table; it must not appear in the create_table inventory.
WITH RankedCustomers AS (SELECT Id FROM Customer) SELECT * FROM RankedCustomers;
