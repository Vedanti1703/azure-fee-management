-- ==============================================================================
-- FeeManagement System - 5,000 Synthetic Student Records
-- Compatible with SQL Server 2022 & Azure SQL Database
-- StudentID starting at 1001 (1001 to 6000)
-- Re-runnable (Idempotent)
-- ==============================================================================

IF SERVERPROPERTY('EngineEdition') <> 5
BEGIN
    USE [FeeManagement];
END
GO

SET NOCOUNT ON;

PRINT 'Populating 5,000 synthetic student records with randomized fees and due dates...';

-- Clean up any previous synthetic range to allow safe re-runs with fresh relative dates
DELETE FROM dbo.Students 
WHERE StudentID BETWEEN 1001 AND 6000;

DECLARE @Today DATE = CAST(GETDATE() AS DATE);

-- Generate numbers 1 to 5000 using CTE
;WITH Digits(N) AS (
    SELECT 0 UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 
    UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9
),
Numbers(N) AS (
    SELECT TOP (5000)
        ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS N
    FROM Digits d1 
    CROSS JOIN Digits d2 
    CROSS JOIN Digits d3 
    CROSS JOIN Digits d4
),
StudentRaw AS (
    SELECT 
        (1000 + n.N) AS StudentID,
        CHOOSE(((n.N % 20) + 1), 
            N'Aarav', N'Aditi', N'Aryan', N'Ananya', N'Dev', 
            N'Diya', N'Ishaan', N'Kavya', N'Manav', N'Meera', 
            N'Nikhil', N'Pooja', N'Pranav', N'Riya', N'Rohan', 
            N'Saanvi', N'Siddharth', N'Sneha', N'Tanmay', N'Varun'
        ) AS FirstName,
        CHOOSE((((n.N * 7) % 20) + 1), 
            N'Sharma', N'Verma', N'Patel', N'Iyer', N'Gupta', 
            N'Nair', N'Kulkarni', N'Joshi', N'Reddy', N'Menon', 
            N'Choudhary', N'Malhotra', N'Singhania', N'Bhattacharya', N'Rao', 
            N'Deshmukh', N'Mukherjee', N'Agarwal', N'Pillai', N'Sengupta'
        ) AS LastName,
        'student' + CAST((1000 + n.N) AS VARCHAR(10)) + '@example.com' AS Email,
        CHOOSE(((n.N % 8) + 1), 
            N'B.Tech Computer Science', 
            N'B.Tech Information Technology', 
            N'B.Tech Electronics & Communication', 
            N'B.Tech Mechanical Engineering', 
            N'B.Tech Civil Engineering', 
            N'M.Tech Data Science', 
            N'MBA Finance', 
            N'MCA'
        ) AS Course,
        CAST((60000.00 + ((n.N * 137 % 61) * 1000.00)) AS DECIMAL(10,2)) AS TotalFee,
        -- Due dates distributed between -60 days (overdue) and +60 days (upcoming)
        DATEADD(DAY, ((n.N * 31 % 121) - 60), @Today) AS DueDate,
        (n.N % 4) AS PaymentBucket,
        ((n.N % 8) + 1) AS PartialFraction
    FROM Numbers n
)
INSERT INTO dbo.Students (StudentID, Name, Email, Course, TotalFee, PaidAmount, DueDate)
SELECT 
    sr.StudentID,
    (sr.FirstName + N' ' + sr.LastName) AS Name,
    sr.Email,
    sr.Course,
    sr.TotalFee,
    CASE 
        -- 25% fully settled
        WHEN sr.PaymentBucket = 0 THEN sr.TotalFee
        -- 25% zero payment
        WHEN sr.PaymentBucket = 1 THEN 0.00
        -- 50% partial payment (10% to 80% of total fee)
        ELSE CAST(ROUND(sr.TotalFee * (sr.PartialFraction / 10.0), 2) AS DECIMAL(10,2))
    END AS PaidAmount,
    sr.DueDate
FROM StudentRaw sr;

DECLARE @InsertedCount INT = @@ROWCOUNT;
PRINT 'Successfully inserted ' + CAST(@InsertedCount AS VARCHAR(10)) + ' synthetic student records (IDs 1001 - 6000).';
GO
