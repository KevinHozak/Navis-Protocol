Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SelectVoice('Microsoft Zira Desktop')
$synth.Speak('Rollover sequence complete. Tactical journal for tomorrow has been initialized with four active mandates.')
