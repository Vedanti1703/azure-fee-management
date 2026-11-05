
-- ==============================================================================
-- FeeManagement System - Seed Data
-- 20 Realistic Indian Student Records + 3 Administrators
-- Re-runnable (Idempotent) using MERGE
-- Azure SQL Database Compatible
-- ==============================================================================

SET NOCOUNT ON;

-- ------------------------------------------------------------------------------
-- 1. Seed Administrators (3 Records)
-- ------------------------------------------------------------------------------

MERGE dbo.Administrators AS target
USING (
    VALUES
        (1, N'Dr. Rajesh Kumar', N'Finance Director'),
        (2, N'Sunita Venkatesh', N'Senior Accounts Officer'),
        (3, N'Amit Saxena', N'Fee Collection Coordinator')
) AS source (AdminID, Name, Role)

ON (target.AdminID = source.AdminID)

WHEN MATCHED THEN
    UPDATE SET
        target.Name = source.Name,
        target.Role = source.Role

WHEN NOT MATCHED BY TARGET THEN
    INSERT (AdminID, Name, Role)
    VALUES (source.AdminID, source.Name, source.Role);

-- ------------------------------------------------------------------------------
-- 2. Seed Students (20 Records)
-- ------------------------------------------------------------------------------

MERGE dbo.Students AS target

USING (
    VALUES

        -- Case A: Fully Paid

        (1, N'Aarav Sharma', N'aarav.sharma@example.com',
         N'B.Tech Computer Science', 85000.00, 85000.00,
         DATEADD(DAY, -20, CAST(GETDATE() AS DATE))),

        (2, N'Diya Patel', N'diya.patel@example.com',
         N'B.Tech Information Technology', 78000.00, 78000.00,
         DATEADD(DAY, -10, CAST(GETDATE() AS DATE))),

        (3, N'Rohan Iyer', N'rohan.iyer@example.com',
         N'B.Tech Electronics & Communication', 82000.00, 82000.00,
         DATEADD(DAY, 15, CAST(GETDATE() AS DATE))),

        (4, N'Ananya Verma', N'ananya.verma@example.com',
         N'M.Tech Data Science', 95000.00, 95000.00,
         DATEADD(DAY, 30, CAST(GETDATE() AS DATE))),

        -- Case B: Partially Paid, Not Yet Due

        (5, N'Vivaan Gupta', N'vivaan.gupta@example.com',
         N'B.Tech Computer Science', 85000.00, 45000.00,
         DATEADD(DAY, 15, CAST(GETDATE() AS DATE))),

        (6, N'Saanvi Nair', N'saanvi.nair@example.com',
         N'B.Tech Mechanical Engineering', 75000.00, 35000.00,
         DATEADD(DAY, 25, CAST(GETDATE() AS DATE))),

        (7, N'Ishan Kulkarni', N'ishan.kulkarni@example.com',
         N'MBA Finance', 120000.00, 60000.00,
         DATEADD(DAY, 35, CAST(GETDATE() AS DATE))),

        (8, N'Meera Joshi', N'meera.joshi@example.com',
         N'B.Tech Artificial Intelligence', 90000.00, 50000.00,
         DATEADD(DAY, 45, CAST(GETDATE() AS DATE))),

        -- Case C: Overdue with Partial Payment

        (9, N'Aditya Deshmukh', N'vedantighanekar+s1@gmail.com',
         N'B.Tech Computer Science', 85000.00, 30000.00,
         DATEADD(DAY, -7, CAST(GETDATE() AS DATE))),

        (10, N'Riya Mukherjee', N'Yvedantighanekar+s2@gmail.com',
         N'B.Tech Electrical Engineering', 78000.00, 25000.00,
         DATEADD(DAY, -15, CAST(GETDATE() AS DATE))),

        (11, N'Arjun Reddy', N'arjun.reddy@example.com',
         N'MBA Finance', 120000.00, 40000.00,
         DATEADD(DAY, -30, CAST(GETDATE() AS DATE))),

        (12, N'Kavya Menon', N'kavya.menon@example.com',
         N'B.Tech Biotechnology', 72000.00, 20000.00,
         DATEADD(DAY, -45, CAST(GETDATE() AS DATE))),

        -- Case D: Overdue with Zero Payment

        (13, N'Siddharth Malhotra', N'vedantighanekar+s3@gmail.com',
         N'B.Tech Computer Science', 85000.00, 0.00,
         DATEADD(DAY, -5, CAST(GETDATE() AS DATE))),

        (14, N'Pooja Choudhary', N'vedantighanekar+s4@gmail.com',
         N'MCA', 70000.00, 0.00,
         DATEADD(DAY, -12, CAST(GETDATE() AS DATE))),

        (15, N'Nikhil Singhania', N'nikhil.singhania@example.com',
         N'B.Tech Mechanical Engineering', 75000.00, 0.00,
         DATEADD(DAY, -25, CAST(GETDATE() AS DATE))),

        (16, N'Shreya Bhattacharya', N'shreya.bhattacharya@example.com',
         N'M.Sc Cyber Security', 80000.00, 0.00,
         DATEADD(DAY, -40, CAST(GETDATE() AS DATE))),

        -- Case E: Not Yet Due with Zero Payment

        (17, N'Tanmay Rao', N'tanmay.rao@example.com',
         N'B.Tech Information Technology', 78000.00, 0.00,
         DATEADD(DAY, 10, CAST(GETDATE() AS DATE))),

        (18, N'Neha Agarwal', N'neha.agarwal@example.com',
         N'B.Tech Chemical Engineering', 74000.00, 0.00,
         DATEADD(DAY, 20, CAST(GETDATE() AS DATE))),

        (19, N'Pranav Pillai', N'pranav.pillai@example.com',
         N'B.Tech Computer Science', 85000.00, 0.00,
         DATEADD(DAY, 30, CAST(GETDATE() AS DATE))),

        (20, N'Sneha Sengupta', N'sneha.sengupta@example.com',
         N'MBA Marketing', 115000.00, 0.00,
         DATEADD(DAY, 50, CAST(GETDATE() AS DATE)))

) AS source
(
    StudentID,
    Name,
    Email,
    Course,
    TotalFee,
    PaidAmount,
    DueDate
)

ON (target.StudentID = source.StudentID)

WHEN MATCHED THEN
    UPDATE SET
        target.Name = source.Name,
        target.Email = source.Email,
        target.Course = source.Course,
        target.TotalFee = source.TotalFee,
        target.PaidAmount = source.PaidAmount,
        target.DueDate = source.DueDate

WHEN NOT MATCHED BY TARGET THEN
    INSERT
    (
        StudentID,
        Name,
        Email,
        Course,
        TotalFee,
        PaidAmount,
        DueDate
    )
    VALUES
    (
        source.StudentID,
        source.Name,
        source.Email,
        source.Course,
        source.TotalFee,
        source.PaidAmount,
        source.DueDate
    );

PRINT 'Successfully seeded 20 students and 3 administrators.';
