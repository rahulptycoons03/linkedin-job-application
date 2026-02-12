*** Settings ***
Documentation     Keywords for LinkedIn Easy Apply (Singapore Data Engineer).
Library           SeleniumLibrary    implicit_wait=5
Library           LinkedInEasyApplyLibrary

*** Keywords ***
Open Browser To LinkedIn
    [Arguments]    ${url}=https://www.linkedin.com
    Open Browser    ${url}    ${BROWSER}
    Maximize Browser Window
    Set Selenium Speed    0.3

Sign In To LinkedIn
    [Documentation]    Sign in using \${USERNAME} and \${PASSWORD}. Skips if already on feed.
    Go To    ${LINKEDIN_LOGIN}
    Sleep    2s
    ${visible}=    Run Keyword And Return Status    Element Should Be Visible    id=username
    Run Keyword If    not ${visible}    Log    Login form not shown; may already be logged in.    level=INFO
    Run Keyword If    ${visible}    Run Keywords
    ...    Input Text    id=username    ${USERNAME}
    ...    AND    Input Text    id=password    ${PASSWORD}
    ...    AND    Click Button    xpath=//button[@type='submit' and contains(., 'Sign in')]
    ...    AND    Sleep    4s
    Run Keyword If    ${visible}    Wait Until Location Contains    linkedin.com    timeout=20s
    Log    LinkedIn sign-in step complete.    level=INFO

Go To LinkedIn Search
    [Arguments]    ${keywords}    ${location}=${LOCATION}
    ${url}=    Build Search Url    ${keywords}    ${location}
    Go To    ${url}
    Sleep    3s
    RETURN    ${url}

Process Job At Index
    [Arguments]    ${index}    ${search_url}
    [Documentation]    Click job card. If not Easy Apply: go back, return SKIP. Else: Easy Apply, go back, return APPLIED or SKIP.
    Click Job Card By Index    ${index}
    ${easy}=    Easy Apply Button Present
    Run Keyword If    not ${easy}    Go Back To Search    ${search_url}
    Run Keyword If    not ${easy}    Log    LinkedIn: no Easy Apply – skipped, back to search.    level=WARN
    Return From Keyword If    not ${easy}    SKIP
    ${ok}=    Try Easy Apply And Submit
    Go Back To Search    ${search_url}
    ${status}=    Set Variable If    ${ok}    APPLIED    SKIP
    Run Keyword If    ${ok}    Log    LinkedIn: applied (Easy Apply).    level=INFO
    Run Keyword Unless    ${ok}    Log    LinkedIn: Easy Apply flow did not complete – skipped.    level=WARN
    RETURN    ${status}
