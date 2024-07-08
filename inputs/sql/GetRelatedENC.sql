-- 'GC11206.zip', 'US4SC22M', 'US4SC22M', 'AVAILABLE', '20', '2016\\GC''
SELECT doc.documenttype, doc.BaseFileName, k.iecode, lk.status, doc.InformationCode, doc.Path
FROM sourcedocument doc
    INNER JOIN affectedkapp aff ON aff.sourceid = doc.sourceid
    INNER JOIN chappkapp k ON k.kappid = aff.kappid
    INNER JOIN chappchart c ON c.chartid = k.chartid
INNER JOIN status_lookup lk ON lk.value = aff.ApplicationStatus
WHERE
    c.ENCCell = 1
    AND doc.documenttype = 'GC'
    -- application status 0,1,2,3,4 == unassigned, assigned, in compilation, in review, review complete (ie not posted)
    AND aff.applicationstatus < 5    
    ---- use status 0 if you only want unassigned
    -- AND aff.applicationstatus = 0
    ---- comment out if you want information code 20, although my query turned up all 20s anyway
    AND doc.InformationCode = '20'
    -- only documents released by NDB, otherwise they are still in work or brought back for correction
    AND doc.Status = 'AVAILABLE'