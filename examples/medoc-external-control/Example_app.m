ip='172.16.10.1';
main(ip, 20121, 0)
pause(0.5)
main(ip, 20121, 1,11000000) %first defined program = ramp and hold
pause(0.5)
main(ip, 20121, 2) %start - pretest
pause(1)
main(ip, 20121, 2,00000010) %start

count=1;
while count<1000
main(ip, 20121, 0)
pause(0.05)
count=count+1;
end


main(ip, 20121, 3) %pause
main(ip, 20121, 5) %stop

main(ip, 20121, 1,01000000) %another defined program = Search

main(ip, 20121, 2) %start - pretest
main(ip, 20121, 2) %start

main(ip, 20121, 7) %Yes

main(ip, 20121, 8) %No

main(ip, 20121, 7) %Yes


main(ip, 20121, 1, 10000000) %another defined program = VAS Search

main(ip, 20121, 4)%Trigger

main(ip, 20121, 12,500) %Increase temp

main(ip, 20121, 14) %Keyup

main(ip, 20121, 13,1000) %Decrease temp
main(ip, 20121, 5) %stop


% command_to_id = {
%     'GET_STATUS':   0,
%     'SELECT_TP':    1,
%     'START':        2,
%     'PAUSE':        3,
%     'TRIGGER':      4,
%     'STOP':         5,
%     'ABORT':        6,
%     'YES':          7,  # used to start increasing the temperature
%     'NO':           8,  # used to start decreasing the temperature
%     'COVAS':        9,
%     'VAS':         10,
%     'SPECIFY_NEXT':11,
%     'T_UP':        12,
%     'T_DOWN':      13,
%     'KEYUP':       14,  # used to stop the temperature gradient,
%     'UNNAMED':     15
% }