-- ==============================================================================
-- Azure Student Fee Management System - Seed Data (Development & QA)
-- ==============================================================================

USE [StudentFeeManagementDB];
GO

SET NOCOUNT ON;

-- ------------------------------------------------------------------------------
-- 1. Seed Courses
-- ------------------------------------------------------------------------------
IF NOT EXISTS (SELECT 1 FROM dbo.Courses WHERE course_code = 'BTECH-CS')
BEGIN
    INSERT INTO dbo.Courses (course_code, course_name, department, duration_semesters, base_fee_per_semester)
    VALUES 
    ('BTECH-CS', 'Bachelor of Technology in Computer Science', 'Engineering', 8, 4500.00),
    ('BTECH-EE', 'Bachelor of Technology in Electrical Engineering', 'Engineering', 8, 4200.00),
    ('MBA-FIN',  'Master of Business Administration (Finance)', 'Business', 4, 6000.00),
    ('BS-DATA',  'Bachelor of Science in Data Science', 'Computing', 6, 4800.00),
    ('MS-CYBER', 'Master of Science in Cybersecurity', 'Computing', 4, 5500.00);
END
GO

-- ------------------------------------------------------------------------------
-- 2. Seed Academic Terms
-- ------------------------------------------------------------------------------
IF NOT EXISTS (SELECT 1 FROM dbo.AcademicTerms WHERE term_code = 'AY2026-FALL')
BEGIN
    INSERT INTO dbo.AcademicTerms (term_code, term_name, academic_year, start_date, end_date, is_active)
    VALUES
    ('AY2026-SPRING', 'Spring 2026 Term', '2025-2026', '2026-01-15', '2026-05-30', 0),
    ('AY2026-FALL',   'Fall 2026 Term',   '2026-2027', '2026-08-20', '2026-12-20', 1),
    ('AY2027-SPRING', 'Spring 2027 Term', '2026-2027', '2027-01-15', '2027-05-30', 0);
END
GO

-- ------------------------------------------------------------------------------
-- 3. Seed Fee Categories
-- ------------------------------------------------------------------------------
IF NOT EXISTS (SELECT 1 FROM dbo.FeeCategories WHERE category_name = 'Tuition Fee')
BEGIN
    INSERT INTO dbo.FeeCategories (category_name, description, is_mandatory)
    VALUES
    ('Tuition Fee', 'Base academic instruction and laboratory sessions', 1),
    ('Technology & Computing Fee', 'Campus Wi-Fi, LMS access, and cloud labs', 1),
    ('Library & Research Fee', 'Digital journal access and physical catalog', 1),
    ('Student Activities Fee', 'Clubs, sports facilities, and cultural events', 0),
    ('Hostel & Accommodation', 'On-campus residence and maintenance', 0);
END
GO

-- ------------------------------------------------------------------------------
-- 4. Seed Initial Sample Students
-- ------------------------------------------------------------------------------
DECLARE @csCourseId INT = (SELECT course_id FROM dbo.Courses WHERE course_code = 'BTECH-CS');
DECLARE @mbaCourseId INT = (SELECT course_id FROM dbo.Courses WHERE course_code = 'MBA-FIN');
DECLARE @dsCourseId INT = (SELECT course_id FROM dbo.Courses WHERE course_code = 'BS-DATA');

IF NOT EXISTS (SELECT 1 FROM dbo.Students WHERE student_code = 'STU-2026-001')
BEGIN
    INSERT INTO dbo.Students (student_code, first_name, last_name, email, phone, course_id, current_semester, enrollment_date, status)
    VALUES
    ('STU-2026-001', 'Alice', 'Walker', 'alice.walker@student.university.edu', '+15550101', @csCourseId, 1, '2026-08-01', 'ACTIVE'),
    ('STU-2026-002', 'Brian', 'Chen', 'brian.chen@student.university.edu', '+15550102', @csCourseId, 3, '2025-08-01', 'ACTIVE'),
    ('STU-2026-003', 'Chloe', 'Patel', 'chloe.patel@student.university.edu', '+15550103', @mbaCourseId, 1, '2026-08-01', 'ACTIVE'),
    ('STU-2026-004', 'David', 'Kim', 'david.kim@student.university.edu', '+15550104', @dsCourseId, 2, '2026-01-10', 'ACTIVE'),
    ('STU-2026-005', 'Elena', 'Rostova', 'elena.rostova@student.university.edu', '+15550105', @csCourseId, 4, '2025-01-10', 'ACTIVE');
END
GO

-- ------------------------------------------------------------------------------
-- 5. Seed Invoices & Items
-- ------------------------------------------------------------------------------
DECLARE @termFallId INT = (SELECT term_id FROM dbo.AcademicTerms WHERE term_code = 'AY2026-FALL');
DECLARE @s1 INT = (SELECT student_id FROM dbo.Students WHERE student_code = 'STU-2026-001');
DECLARE @s2 INT = (SELECT student_id FROM dbo.Students WHERE student_code = 'STU-2026-002');
DECLARE @s3 INT = (SELECT student_id FROM dbo.Students WHERE student_code = 'STU-2026-003');

DECLARE @catTuition INT = (SELECT category_id FROM dbo.FeeCategories WHERE category_name = 'Tuition Fee');
DECLARE @catTech INT = (SELECT category_id FROM dbo.FeeCategories WHERE category_name = 'Technology & Computing Fee');
DECLARE @catLib INT = (SELECT category_id FROM dbo.FeeCategories WHERE category_name = 'Library & Research Fee');

-- Invoice 1: Overdue Invoice for Student 1
IF NOT EXISTS (SELECT 1 FROM dbo.Invoices WHERE invoice_number = 'INV-2026-0001')
BEGIN
    INSERT INTO dbo.Invoices (invoice_number, student_id, term_id, total_amount, paid_amount, due_date, status, notes)
    VALUES ('INV-2026-0001', @s1, @termFallId, 4850.00, 0.00, DATEADD(DAY, -5, CAST(GETUTCDATE() AS DATE)), 'OVERDUE', 'Fall 2026 Semester Regular Fee');

    DECLARE @inv1 INT = SCOPE_IDENTITY();
    INSERT INTO dbo.InvoiceItems (invoice_id, category_id, description, amount)
    VALUES 
    (@inv1, @catTuition, 'BTech Computer Science Tuition', 4500.00),
    (@inv1, @catTech, 'Campus Computing Services', 250.00),
    (@inv1, @catLib, 'Library Digital Subscriptions', 100.00);
END

-- Invoice 2: Partially Paid Invoice for Student 2
IF NOT EXISTS (SELECT 1 FROM dbo.Invoices WHERE invoice_number = 'INV-2026-0002')
BEGIN
    INSERT INTO dbo.Invoices (invoice_number, student_id, term_id, total_amount, paid_amount, due_date, status, notes)
    VALUES ('INV-2026-0002', @s2, @termFallId, 4850.00, 2000.00, DATEADD(DAY, 10, CAST(GETUTCDATE() AS DATE)), 'PARTIAL', 'Installment 1 Received');

    DECLARE @inv2 INT = SCOPE_IDENTITY();
    INSERT INTO dbo.InvoiceItems (invoice_id, category_id, description, amount)
    VALUES 
    (@inv2, @catTuition, 'BTech Computer Science Tuition', 4500.00),
    (@inv2, @catTech, 'Campus Computing Services', 250.00),
    (@inv2, @catLib, 'Library Digital Subscriptions', 100.00);

    -- Seed payment for Invoice 2
    INSERT INTO dbo.Payments (transaction_reference, invoice_id, amount_paid, payment_method, payment_status, payment_date, notes)
    VALUES ('TXN-20260901-0001', @inv2, 2000.00, 'ONLINE_PORTAL', 'SUCCESS', DATEADD(DAY, -3, SYSUTCDATETIME()), 'First installment payment via NetBanking');
END

-- Invoice 3: Fully Paid Invoice for Student 3
IF NOT EXISTS (SELECT 1 FROM dbo.Invoices WHERE invoice_number = 'INV-2026-0003')
BEGIN
    INSERT INTO dbo.Invoices (invoice_number, student_id, term_id, total_amount, paid_amount, due_date, status, notes)
    VALUES ('INV-2026-0003', @s3, @termFallId, 6350.00, 6350.00, DATEADD(DAY, 15, CAST(GETUTCDATE() AS DATE)), 'PAID', 'Full payment settled');

    DECLARE @inv3 INT = SCOPE_IDENTITY();
    INSERT INTO dbo.InvoiceItems (invoice_id, category_id, description, amount)
    VALUES 
    (@inv3, @catTuition, 'MBA Finance Tuition', 6000.00),
    (@inv3, @catTech, 'Business Analytics Lab Fee', 250.00),
    (@inv3, @catLib, 'Harvard Business Review Case Access', 100.00);

    -- Seed payment for Invoice 3
    INSERT INTO dbo.Payments (transaction_reference, invoice_id, amount_paid, payment_method, payment_status, payment_date, notes)
    VALUES ('TXN-20260902-0002', @inv3, 6350.00, 'CREDIT_CARD', 'SUCCESS', DATEADD(DAY, -2, SYSUTCDATETIME()), 'Full tuition payment processed via Stripe/Visa');
END
GO

PRINT 'Initial seed data populated successfully.';
GO

