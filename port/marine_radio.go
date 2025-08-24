package main

import (
    "errors"
    "fmt" 
    "net/http"
    "os"
	"os/signal"
	"syscall"
)

var FREQUENCY = "0.0.0.0:1566"
var PAN_PAN = false

func handleRadioSignal(w http.ResponseWriter, r *http.Request) {
    if (PAN_PAN) {
		w.WriteHeader(http.StatusInternalServerError)
    } else {
		w.WriteHeader(http.StatusOK)
    }
}

func main() {
    // SIGUSR1 activates PAN-PAN signal
	usr1Sigs := make(chan os.Signal, 1)
	signal.Notify(usr1Sigs, syscall.SIGUSR1)
    go func(){
        for range usr1Sigs {
            PAN_PAN = true
        }
    }()

    // SIGUSR2 deactivates PAN-PAN signal
	usr2Sigs := make(chan os.Signal, 1)
	signal.Notify(usr2Sigs, syscall.SIGUSR2)
    go func(){
        for range usr2Sigs {
            PAN_PAN = false
        }
    }()

    http.HandleFunc("/", handleRadioSignal)

    err := http.ListenAndServe(FREQUENCY, nil)

    if errors.Is(err, http.ErrServerClosed) {
        fmt.Printf("Radio turned off\n")
    } else if err != nil {
        fmt.Printf("Radio broken, error code: %s\n", err)
        os.Exit(1)
    }
}