-- ==============================================================================
-- Azure Student Fee Management System - 5,000 High-Volume Synthetic Records
-- For Performance, Index Tuning, and Load Testing
-- ==============================================================================

USE [StudentFeeManagementDB];
GO

SET NOCOUNT ON;

PRINT 'Starting generation of 5,000 synthetic students and invoices...';

-- Ensure baseline reference data exists
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

IF NOT EXISTS (SELECT 1 FROM dbo.AcademicTerms WHERE term_code = 'AY2026-FALL')
BEGIN
    INSERT INTO dbo.AcademicTerms (term_code, term_name, academic_year, start_date, end_date, is_active)
    VALUES ('AY2026-FALL', 'Fall 2026 Term', '2026-2027', '2026-08-20', '2026-12-20', 1);
END

IF NOT EXISTS (SELECT 1 FROM dbo.FeeCategories WHERE category_name = 'Tuition Fee')
BEGIN
    INSERT INTO dbo.FeeCategories (category_name, description, is_mandatory)
    VALUES
    ('Tuition Fee', 'Base academic instruction', 1),
    ('Technology & Computing Fee', 'Campus Wi-Fi and LMS', 1),
    ('Library & Research Fee', 'Digital journal access', 1);
END
GO

-- ------------------------------------------------------------------------------
-- Fast Tally Table / CTE to generate 5,000 records
-- ------------------------------------------------------------------------------
BEGIN TRANSACTION;

BEGIN TRY
    -- Capture reference IDs
    DECLARE @termId INT = (SELECT TOP 1 term_id FROM dbo.AcademicTerms WHERE term_code = 'AY2026-FALL');
    DECLARE @catTuitionId INT = (SELECT TOP 1 category_id FROM dbo.FeeCategories WHERE category_name = 'Tuition Fee');
    DECLARE @catTechId INT = (SELECT TOP 1 category_id FROM dbo.FeeCategories WHERE category_name = 'Technology & Computing Fee');

    -- Temporary table for course ID lookup
    DECLARE @CoursesTable TABLE (id INT IDENTITY(1,1), course_id INT, base_fee DECIMAL(12,2));
    INSERT INTO @CoursesTable (course_id, base_fee)
    SELECT course_id, base_fee_per_semester FROM dbo.Courses WHERE is_active = 1;

    DECLARE @CourseCount INT = (SELECT COUNT(*) FROM @CoursesTable);

    -- Generate Numbers 1 to 5000 using CTE
    ;WITH Digits(N) AS (
        SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 
        UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9 UNION ALL SELECT 0
    ),
    Numbers(N) AS (
        SELECT TOP (5000)
            ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS N
        FROM Digits d1 
        CROSS JOIN Digits d2 
        CROSS JOIN Digits d3 
        CROSS JOIN Digits d4
    ),
    StudentGen AS (
        SELECT 
            N,
            'STU-SYNTH-' + RIGHT('00000' + CAST(N AS VARCHAR(5)), 5) AS student_code,
            CHOOSE(((N % 10) + 1), 'Alex', 'Liam', 'Olivia', 'Emma', 'Noah', 'Sophia', 'James', 'Mia', 'Lucas', 'Amelia') AS first_name,
            CHOOSE(((N % 10) + 1), 'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez') AS last_name,
            'student' + CAST(N AS VARCHAR(10)) + '@loadtest.university.edu' AS email,
            '+1555' + RIGHT('000000' + CAST(N AS VARCHAR(6)), 6) AS phone,
            ((N % @CourseCount) + 1) AS course_slot,
            ((N % 8) + 1) AS current_semester,
            DATEADD(DAY, -(N % 700), CAST(GETUTCDATE() AS DATE)) AS enrollment_date
        FROM Numbers
    )
    -- Insert only records not already present
    INSERT INTO dbo.Students (student_code, first_name, last_name, email, phone, course_id, current_semester, enrollment_date, status)
    SELECT 
        sg.student_code,
        sg.first_name,
        sg.last_name,
        sg.email,
        sg.phone,
        ct.course_id,
        sg.current_semester,
        sg.enrollment_date,
        'ACTIVE'
    FROM StudentGen sg
    INNER JOIN @CoursesTable ct ON ct.id = sg.course_slot
    WHERE NOT EXISTS (
        SELECT 1 FROM dbo.Students s WHERE s.student_code = sg.student_code
    );

    PRINT '5,000 Students populated.';

    -- --------------------------------------------------------------------------
    -- Generate Corresponding Invoices for each synthetic student
    -- --------------------------------------------------------------------------
    ;WITH SynthStudents AS (
        SELECT 
            s.student_id,
            s.student_code,
            c.base_fee_per_semester,
            ROW_NUMBER() OVER (ORDER BY s.student_id) AS row_num
        FROM dbo.Students s
        INNER JOIN dbo.Courses c ON s.course_id = c.course_id
        WHERE s.student_code LIKE 'STU-SYNTH-%'
          AND NOT EXISTS (
              SELECT 1 FROM dbo.Invoices i WHERE i.student_id = s.student_id AND i.term_id = @termId
          )
    )
    INSERT INTO dbo.Invoices (invoice_number, student_id, term_id, total_amount, paid_amount, due_date, status, notes)
    SELECT 
        'INV-SYNTH-' + RIGHT('00000' + CAST(ss.row_num AS VARCHAR(5)), 5),
        ss.student_id,
        @termId,
        ss.base_fee_per_semester + 250.00, -- Base tuition + 250 Tech fee
        CASE 
            WHEN ss.row_num % 4 = 0 THEN ss.base_fee_per_semester + 250.00 -- 25% fully paid
            WHEN ss.row_num % 4 = 1 THEN 1500.00                           -- 25% partially paid
            ELSE 0.00                                                      -- 50% pending or overdue
        END AS paid_amount,
        DATEADD(DAY, (ss.row_num % 60) - 30, CAST(GETUTCDATE() AS DATE)) AS due_date,
        CASE 
            WHEN ss.row_num % 4 = 0 THEN 'PAID'
            WHEN ss.row_num % 4 = 1 THEN 'PARTIAL'
            WHEN (ss.row_num % 60) - 30 < 0 THEN 'OVERDUE'
            ELSE 'PENDING'
        END AS status,
        'Synthetic load test invoice for Fall 2026'
    FROM SynthStudents ss;

    PRINT 'Invoices populated for synthetic students.';

    -- --------------------------------------------------------------------------
    -- Generate Line Items for synthetic invoices
    -- --------------------------------------------------------------------------
    INSERT INTO dbo.InvoiceItems (invoice_id, category_id, description, amount)
    SELECT 
        inv.invoice_id,
        @catTuitionId,
        'Tuition fee (Course semester rate)',
        inv.total_amount - 250.00
    FROM dbo.Invoices inv
    WHERE inv.invoice_number LIKE 'INV-SYNTH-%'
      AND NOT EXISTS (SELECT 1 FROM dbo.InvoiceItems ii WHERE ii.invoice_id = inv.invoice_id);

    INSERT INTO dbo.InvoiceItems (invoice_id, category_id, description, amount)
    SELECT 
        inv.invoice_id,
        @catTechId,
        'Campus Technology Fee',
        250.00
    FROM dbo.Invoices inv
    WHERE inv.invoice_number LIKE 'INV-SYNTH-%'
      AND (SELECT COUNT(*) FROM dbo.InvoiceItems ii WHERE ii.invoice_id = inv.invoice_id) = 1;

    -- --------------------------------------------------------------------------
    -- Generate Payments for Paid / Partial Invoices
    -- --------------------------------------------------------------------------
    INSERT INTO dbo.Payments (transaction_reference, invoice_id, amount_paid, payment_method, payment_status, payment_date, notes)
    SELECT 
        'TXN-SYNTH-' + RIGHT('000000' + CAST(inv.invoice_id AS VARCHAR(6)), 6),
        inv.invoice_id,
        inv.paid_amount,
        'ONLINE_PORTAL',
        'SUCCESS',
        DATEADD(DAY, -5, SYSUTCDATETIME()),
        'Auto-generated synthetic payment transaction'
    FROM dbo.Invoices inv
    WHERE inv.invoice_number LIKE 'INV-SYNTH-%'
      AND inv.paid_amount > 0
      AND NOT EXISTS (SELECT 1 FROM dbo.Payments p WHERE p.invoice_id = inv.invoice_id);

    COMMIT TRANSACTION;
    PRINT 'Synthetic 5,000 dataset loaded and committed successfully.';

END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;

    PRINT 'Error occurred during 5,000 seed population: ' + ERROR_MESSAGE();
    THROW;
END CATCH;
GO

