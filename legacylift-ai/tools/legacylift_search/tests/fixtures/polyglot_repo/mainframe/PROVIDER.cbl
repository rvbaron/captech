       IDENTIFICATION DIVISION.
       PROGRAM-ID. PROVIDER.

       PROCEDURE DIVISION.
       MAIN-PROCESSING.
           PERFORM VALIDATE-PROVIDER.
           PERFORM UPDATE-RECORDS.
           STOP RUN.

       VALIDATE-PROVIDER.
           DISPLAY 'Validating provider'.
           CALL 'ELIGIBILITY-CHECK'.

       UPDATE-RECORDS.
           DISPLAY 'Updating provider records'.
           PERFORM WRITE-DATABASE.

       WRITE-DATABASE.
           DISPLAY 'Writing to database'.
