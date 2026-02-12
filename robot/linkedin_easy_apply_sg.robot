*** Settings ***
Documentation     LinkedIn Easy Apply - Singapore Data Engineer (rahul-sg). Robot + Selenium Chrome.
Variables         vars_linkedin_sg.py
Resource          LinkedInKeywords.robot

*** Test Cases ***
LinkedIn Easy Apply Singapore Data Engineer
    [Documentation]    Sign in, search data engineer jobs in Singapore (Easy Apply only), apply to Easy Apply jobs. Skip non-Easy Apply.
    Open Browser To LinkedIn    ${LINKEDIN_HOME}
    Sign In To LinkedIn
    ${applied}=    Set Variable    0
    FOR    ${kw}    IN    @{KEYWORDS}
        Exit For Loop If    ${applied} >= ${MAX_APPLICATIONS}
        ${search_url}=    Go To LinkedIn Search    ${kw}
        ${indices}=    Get Easy Apply Card Indices
        FOR    ${idx}    IN    @{indices}
            Exit For Loop If    ${applied} >= ${MAX_APPLICATIONS}
            ${status}=    Process Job At Index    ${idx}    ${search_url}
            ${add}=    Evaluate    1 if '${status}' == 'APPLIED' else 0
            ${applied}=    Evaluate    ${applied} + ${add}
        END
    END
    Log    LinkedIn Easy Apply (SG) complete. Total applications: ${applied}.    level=INFO
    [Teardown]    Close Browser
