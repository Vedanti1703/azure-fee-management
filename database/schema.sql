-- ==============================================================================
-- FeeManagement System - Database Schema
-- Compatible with SQL Server 2022 & Azure SQL Database
-- ==============================================================================

-- 1. Create Database if not running inside Azure SQL Database (where DB is pre-provisioned)
IF SERVERPROPERTY('EngineEdition') <> 5
BEGIN
    IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'FeeManagement')
    BEGIN
        CREATE DATABASE [FeeManagement];
    END
END
GO

IF SERVERPROPERTY('EngineEdition') <> 5
BEGIN
    USE [FeeManagement];
END
GO

-- ------------------------------------------------------------------------------
-- 2. Students Table
-- ------------------------------------------------------------------------------
IF OBJECT_ID(N'dbo.Students', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Students (
        StudentID   INT NOT NULL,
        Name        NVARCHAR(100) NOT NULL,
        Email       NVARCHAR(150) NOT NULL,
        Course      NVARCHAR(100) NULL,
        TotalFee    DECIMAL(10,2) NOT NULL,
        PaidAmount  DECIMAL(10,2) NOT NULL CONSTRAINT DF_Students_PaidAmount DEFAULT (0),
        DueDate     DATE NOT NULL,
        CONSTRAINT PK_Students PRIMARY KEY CLUSTERED (StudentID),
        CONSTRAINT CK_Students_TotalFee CHECK (TotalFee >= 0),
        CONSTRAINT CK_Students_PaidAmount CHECK (PaidAmount >= 0),
        CONSTRAINT CK_Students_PaidVsTotal CHECK (PaidAmount <= TotalFee)
    );
END
GO

-- ------------------------------------------------------------------------------
-- 3. Administrators Table
-- ------------------------------------------------------------------------------
IF OBJECT_ID(N'dbo.Administrators', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Administrators (
        AdminID INT NOT NULL,
        Name    NVARCHAR(100) NULL,
        Role    NVARCHAR(50) NULL,
        CONSTRAINT PK_Administrators PRIMARY KEY CLUSTERED (AdminID)
    );
END
GO

-- ------------------------------------------------------------------------------
-- 4. Nonclustered Index on Students(DueDate)
--    Includes TotalFee, PaidAmount, Email, Name for covering index query optimization
-- ------------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes 
    WHERE name = N'IX_Students_DueDate' 
      AND object_id = OBJECT_ID(N'dbo.Students')
)
BEGIN
    CREATE NONCLUSTERED INDEX IX_Students_DueDate
    ON dbo.Students (DueDate)
    INCLUDE (TotalFee, PaidAmount, Email, Name);
END
GO

-- ------------------------------------------------------------------------------
-- 5. Stored Procedure: sp_GetOverdueStudents
--    Returns overdue students with DueDate < today and outstanding balance,
--    ordered by DueDate with OFFSET / FETCH pagination.
-- ------------------------------------------------------------------------------
CREATE OR ALTER PROCEDURE dbo.sp_GetOverdueStudents
    @Top  INT = 50,
    @Skip INT = 0
AS
BEGIN
    SET NOCOUNT ON;

    -- Ensure non-negative pagination parameters
    IF @Top IS NULL OR @Top <= 0
        SET @Top = 50;

    IF @Skip IS NULL OR @Skip < 0
        SET @Skip = 0;

    SELECT 
        StudentID,
        Name,
        Email,
        Course,
        TotalFee,
        PaidAmount,
        DueDate,
        CAST((TotalFee - PaidAmount) AS DECIMAL(10,2)) AS BalanceAmount
    FROM dbo.Students
    WHERE DueDate < CAST(GETDATE() AS DATE)
      AND PaidAmount < TotalFee
    ORDER BY DueDate ASC, StudentID ASC
    OFFSET @Skip ROWS
    FETCH NEXT @Top ROWS ONLY;
END;
GO
