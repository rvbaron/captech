/*
 * Shaped exactly like an SSMS "Script Objects" / script-folder export, which is
 * how real SQL Server schemas reach us (ExecPlan sql-extractor-temp-cte-fk, M5 —
 * found re-indexing customer.ple.nng.db.ETSPii, where all 143 tables and all 81
 * foreign keys take this form).
 *
 * Two things here are absent from the hand-written fixtures and each broke a
 * different half of the extractor:
 *
 *   1. EVERY data type is bracket-quoted: `[STATE_FIPS] [varchar] (2) NOT NULL`.
 *      The recovery column regex required a bare-word type, so it matched no
 *      column entry at all and every table came out with ZERO columns.
 *   2. Constraints are declared OUT OF LINE, in their own trailing `ALTER TABLE`
 *      batch rather than inside the CREATE TABLE body. Both FK scans only ever
 *      looked inside a CREATE TABLE, so the schema yielded ZERO foreign keys.
 *
 * Also note the `GO` batch separators, the `ON [filegroup]` clauses, and the
 * space between the type and its length — all standard SSMS output.
 */
CREATE TABLE [dbo].[FipsState]
(
[STATE_FIPS] [varchar] (2) NOT NULL,
[STATE_NAME] [varchar] (48) NOT NULL,
[Status] [char] (1) NULL
) ON [app_fg]
GO
CREATE TABLE [dbo].[FipsCounty]
(
[FIPS] [varchar] (5) NOT NULL,
[COUNTY_NAME] [varchar] (48) NOT NULL,
[STATE_FIPS] [varchar] (2) NOT NULL,
[Name] [nvarchar] (100) NULL,
[Value] [decimal] (9, 3) NULL
) ON [app_fg]
GO
CREATE TABLE [dbo].[FipsCity]
(
[PLACE_FIPS] [varchar] (5) NOT NULL,
[CITY_NAME] [varchar] (48) NOT NULL,
[FIPS] [varchar] (5) NOT NULL,
[STATE_FIPS] [varchar] (2) NOT NULL,
[phone] [dbo].[PhoneNumber] NULL,
[systemAssignedKey] [int] IDENTITY(1, 1) NOT NULL
) ON [app_fg]
GO
ALTER TABLE [dbo].[FipsCounty] ADD CONSTRAINT [PK_FipsCounty] PRIMARY KEY CLUSTERED ([FIPS]) ON [app_fg]
GO
ALTER TABLE [dbo].[FipsCounty] ADD CONSTRAINT [FK_County_State] FOREIGN KEY ([STATE_FIPS]) REFERENCES [dbo].[FipsState] ([STATE_FIPS])
GO
ALTER TABLE [dbo].[FipsCity] WITH CHECK ADD CONSTRAINT [FK_City_County] FOREIGN KEY ([FIPS]) REFERENCES [dbo].[FipsCounty] ([FIPS])
GO
ALTER TABLE [dbo].[FipsCity] ADD CONSTRAINT [FK_City_State] FOREIGN KEY ([STATE_FIPS]) REFERENCES [dbo].[FipsState] ([STATE_FIPS])
GO
-- A retired constraint. Must not become an edge.
-- ALTER TABLE [dbo].[FipsCity] ADD CONSTRAINT [FK_City_Ghost] FOREIGN KEY ([FIPS]) REFERENCES [dbo].[GhostTable] ([FIPS])
GO
