$modules = @("device_label","dmx_config","control","sensors","maintenance","info","slots","modes","lamp","display","position","power","self_test","presets","system")
$jobs = foreach ($m in $modules) {
  Start-ThreadJob -ScriptBlock {
    param($mod)
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
      $r = Invoke-RestMethod -Uri "http://127.0.0.1:8000/devices/056C4729D469/modules/$mod/state" -Method Get
      "$mod OK $($sw.Elapsed.TotalSeconds)s"
    } catch {
      "$mod FAILED $($_.Exception.Message) $($sw.Elapsed.TotalSeconds)s"
    }
  } -ArgumentList $m
}
$jobs | Wait-Job | Receive-Job
$jobs | Remove-Job
