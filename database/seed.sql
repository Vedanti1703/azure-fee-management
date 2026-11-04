-- ==============================================================================
-- FeeManagement System - Seed Data
-- 20 Realistic Indian Student Records covering all fee status cases + 3 Admins
-- Re-runnable (Idempotent) using MERGE
-- ==============================================================================

IF SERVERPROPERTY('EngineEdition') <> 5
BEGIN
    USE [FeeManagement];
END
GO

SET NOCOUNT ON;

-- ------------------------------------------------------------------------------
-- 1. Seed Administrators (3 Records)
-- ------------------------------------------------------------------------------
MERGE dbo.Administrators AS target
USING (
    VALUES
        (1, N'Dr. Rajesh Kumar',    N'Finance Director'),
        (2, N'Sunita Venkatesh',    N'Senior Accounts Officer'),
        (3, N'Amit Saxena',         N'Fee Collection Coordinator')
) AS source (AdminID, Name, Role)
ON (target.AdminID = source.AdminID)
WHEN MATCHED THEN
    UPDATE SET 
        target.Name = source.Name,
        target.Role = source.Role
WHEN NOT MATCHED BY TARGET THEN
    INSERT (AdminID, Name, Role)
    VALUES (source.AdminID, source.Name, source.Role);
GO

-- ------------------------------------------------------------------------------
-- 2. Seed Students (20 Records covering all 5 scenarios)
--    Cases:
--      A) Fully Paid (PaidAmount = TotalFee)
--      B) Partially Paid (Not yet due: DueDate > Today, 0 < PaidAmount < TotalFee)
--      C) Overdue with Partial Payment (DueDate < Today, 0 < PaidAmount < TotalFee)
--      D) Overdue with Zero Payment (DueDate < Today, PaidAmount = 0)
--      E) Not yet due with Zero Payment (DueDate > Today, PaidAmount = 0)
--
--    Note: Rows with StudentID 9, 10, 13, 14 contain test email placeholders:
--          YOUR_EMAIL+s1@gmail.com, YOUR_EMAIL+s2@gmail.com, etc.
-- ------------------------------------------------------------------------------
DECLARE @Today DATE = CAST(GETDATE() AS DATE);

MERGE dbo.Students AS target
USING (
    VALUES
        -- Case A: Fully Paid (PaidAmount = TotalFee)
        (1,  N'Aarav Sharma',         N'aarav.sharma@example.com',        N'B.Tech Computer Science',            85000.00, 85000.00, DATEADD(DAY, -20, @Today)),
        (2,  N'Diya Patel',           N'diya.patel@example.com',          N'B.Tech Information Technology',      78000.00, 78000.00, DATEADD(DAY, -10, @Today)),
        (3,  N'Rohan Iyer',           N'rohan.iyer@example.com',          N'B.Tech Electronics & Communication', 82000.00, 82000.00, DATEADD(DAY,  15, @Today)),
        (4,  N'Ananya Verma',         N'ananya.verma@example.com',        N'M.Tech Data Science',                95000.00, 95000.00, DATEADD(DAY,  30, @Today)),

        -- Case B: Partially Paid, Not Yet Due (0 < PaidAmount < TotalFee, DueDate > Today)
        (5,  N'Vivaan Gupta',         N'vivaan.gupta@example.com',        N'B.Tech Computer Science',            85000.00, 45000.00, DATEADD(DAY,  15, @Today)),
        (6,  N'Saanvi Nair',          N'saanvi.nair@example.com',         N'B.Tech Mechanical Engineering',      75000.00, 35000.00, DATEADD(DAY,  25, @Today)),
        (7,  N'Ishan Kulkarni',       N'ishan.kulkarni@example.com',      N'MBA Finance',                       120000.00, 60000.00, DATEADD(DAY,  35, @Today)),
        (8,  N'Meera Joshi',          N'meera.joshi@example.com',         N'B.Tech Artificial Intelligence',     90000.00, 50000.00, DATEADD(DAY,  45, @Today)),

        -- Case C: Overdue with Partial Payment (DueDate < Today, 0 < PaidAmount < TotalFee)
        (9,  N'Aditya Deshmukh',      N'YOUR_EMAIL+s1@gmail.com',         N'B.Tech Computer Science',            85000.00, 30000.00, DATEADD(DAY,  -7, @Today)),
        (10, N'Riya Mukherjee',       N'YOUR_EMAIL+s2@gmail.com',         N'B.Tech Electrical Engineering',      78000.00, 25000.00, DATEADD(DAY, -15, @Today)),
        (11, N'Arjun Reddy',          N'arjun.reddy@example.com',         N'MBA Finance',                       120000.00, 40000.00, DATEADD(DAY, -30, @Today)),
        (12, N'Kavya Menon',          N'kavya.menon@example.com',         N'B.Tech Biotechnology',               72000.00, 20000.00, DATEADD(DAY, -45, @Today)),

        -- Case D: Overdue with Zero Payment (DueDate < Today, PaidAmount = 0)
        (13, N'Siddharth Malhotra',   N'YOUR_EMAIL+s3@gmail.com',         N'B.Tech Computer Science',            85000.00,     0.00, DATEADD(DAY,  -5, @Today)),
        (14, N'Pooja Choudhary',      N'YOUR_EMAIL+s4@gmail.com',         N'MCA',                                70000.00,     0.00, DATEADD(DAY, -12, @Today)),
        (15, N'Nikhil Singhania',     N'nikhil.singhania@example.com',    N'B.Tech Mechanical Engineering',      75000.00,     0.00, DATEADD(DAY, -25, @Today)),
        (16, N'Shreya Bhattacharya',  N'shreya.bhattacharya@example.com', N'M.Sc Cyber Security',                80000.00,     0.00, DATEADD(DAY, -40, @Today)),

        -- Case E: Not Yet Due with Zero Payment (DueDate > Today, PaidAmount = 0)
        (17, N'Tanmay Rao',           N'tanmay.rao@example.com',          N'B.Tech Information Technology',      78000.00,     0.00, DATEADD(DAY,  10, @Today)),
        (18, N'Neha Agarwal',         N'neha.agarwal@example.com',        N'B.Tech Chemical Engineering',        74000.00,     0.00, DATEADD(DAY,  20, @Today)),
        (19, N'Pranav Pillai',        N'pranav.pillai@example.com',       N'B.Tech Computer Science',            85000.00,     0.00, DATEADD(DAY,  30, @Today)),
        (20, N'Sneha Sengupta',       N'sneha.sengupta@example.com',      N'MBA Marketing',                     115000.00,     0.00, DATEADD(DAY,  50, @Today))
) AS source (StudentID, Name, Email, Course, TotalFee, PaidAmount, DueDate)
ON (target.StudentID = source.StudentID)
WHEN MATCHED THEN
    UPDATE SET 
        target.Name       = source.Name,
        target.Email      = source.Email,
        target.Course     = source.Course,
        target.TotalFee   = source.TotalFee,
        target.PaidAmount = source.PaidAmount,
        target.DueDate    = source.DueDate
WHEN NOT MATCHED BY TARGET THEN
    INSERT (StudentID, Name, Email, Course, TotalFee, PaidAmount, DueDate)
    VALUES (source.StudentID, source.Name, source.Email, source.Course, source.TotalFee, source.PaidAmount, source.DueDate);
GO

PRINT 'Successfully seeded 20 realistic student records and 3 administrators.';
GO
