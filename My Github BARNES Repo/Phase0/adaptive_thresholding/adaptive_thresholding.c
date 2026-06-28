#include <string.h>
#include "sdkconfig.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "esp_adc/adc_oneshot.h"
#include "hal/adc_types.h"

#include "esp_adc/adc_cali_scheme.h"
#include "esp_adc/adc_cali.h"

#include <math.h>

//LOOK INTO THE WINDOW RATE AND SAMPLING RATE

//PWM pins
#define thumb_en_channel LEDC_CHANNEL_0
/*
#define index_en_channel LEDC_CHANNEL_1
#define middle_en_channel LEDC_CHANNEL_2
#define ring_en_channel LEDC_CHANNEL_3
#define pinky_en_channel LEDC_CHANNEL_4
*/

#define LEDC_TIMER LEDC_TIMER_0
#define LEDC_MODE LEDC_LOW_SPEED_MODE
#define LEDC_DUTY_RES LEDC_TIMER_10_BIT //pwm resolution is 10 bits so the duty cycle ranges from 0 to 1023
#define LEDC_FREQUENCY 20000 //defines the pwm frequency 


//GPIO pins for motor direction control
#define thumb_f
#define thumb_b

/*
#define index_f
#define index_b

#define middle_f
#define middle_b

#define ring_f
#define ring_b

#define pinky_f
#define pinky_b
*/

//PWM pins for position control
#define thumb_en 
/*
#define index_en
#define middle_en
#define ring_en
#define pinky_en
*/

/*
#define OPEN_ANGLE   20 //define the angle based on the servo position in open and close states 
#define CLOSE_ANGLE  160


#define MG90S_MIN_DUTY 123   // 0.6 ms
#define MG90S_MAX_DUTY 491 
*/

/*---------------------PINS FOR ADAPTIVE THRESHOLDING----------------*/
#define L 200 //Number of samples for calculating mean value of RMS
#define alpha 1.5f//represents what %of the mean value of rms the thresh is
#define beta 0.8f//for lower thresh
float rms_val[L]; //Do some more research on how to decide the optimal window length and how it will affect our model
int index2=0;
float thresh;
float lower_thresh; //Use this to avoid constant toggling if the signal oscillates around the threshold
float rms_sum=0;
float rms_mean=0;
int count, count_2=0;
int thresh_count=0;

bool muscle_state = false; //false corresponds to open while true corresponds to close
bool muscle_active= false;
bool active_toggle = false;
bool calib_done=false;

int sampling_freq;//700 hz
float prev_rms=0;

int calib_array[L];
int emg_read, emg_output;
//emg read will hold the raw adc sample
//emg_output will hold the calibrated value in millivolts after conversion.
 
#define N  140//Number of samples for calculation of rms
//Optimal window length for EMG signal analysis as described in a research paper is 150-250 ms so the number of samples will be chosen accoridngly

//Constants for calculating the RMS values
float sum_sq = 0;
float rms = 0;

int index=0;
float hold_array[N];


//Updating the rms value with each incoming sample
float update_rms(float x)
{
  
  prev_rms = rms;
  sum_sq= sum_sq - hold_array[index];
  hold_array[index]= x*x;
  sum_sq= sum_sq+ x*x;
  index = (index+1)%N;
  
  if(count<N)
  {
    count++;
  }
  if(count==N)
  {
    rms = sqrt(sum_sq/N);
    if(!calib_done && thresh_count<L)
    {
        calib_array[thresh_count]=rms; ///Check the indexing again
        thresh_count++;
    }
    else if(thresh_count==L)
    {
        thresh_calib();
        calib_done = true;
        printf("Calibration successful"); //let the print function initially be for testing, remove after that
    }
    
  }
   
  return rms;
}

void thresh_calib() //L samples are taken to calibrate the base value
{
    rms_sum=0;
    for(int i=0;i<L;i++)
    {
        rms_sum= rms_sum + calib_array[i];
    }
    rms_mean= rms_sum/L;
    thresh = alpha*(rms_mean);
    lower_thresh = beta*(rms_mean);
}

void update_muscle_active()
{
    if(rms<lower_thresh)
    {
        muscle_active = false;
    }
    
    else if(muscle_active == false && rms>thresh)
    {
        muscle_active = true;
    }

}

void thresh_update()
{
    
  if(muscle_active == false)
  {

   rms_val[index2] = log(rms + 1e-6);
   index2 = (index2+1)%L;
   count_2=count_2+1;
   rms_sum=0;
  if(count_2==L)
  {
    for(int i=0;i<L;i++)
    {
        rms_sum= rms_sum+ rms_val[i];
    }
    rms_mean= rms_sum/L;
    rms_sum=0;
  }
  thresh = alpha*(rms_mean);
  lower_thresh = beta*(rms_mean);
   }
}

void toggle_detect()
{
    if(prev_rms< lower_thresh && rms>thresh) 
    {
        active_toggle = true;
        muscle_active = true;

    }
    else
    {
        active_toggle= false;
    }
}


void update_muscle_state()
{
    
 if(muscle_state == false && active_toggle == true)
 {
    muscle_state = true; //Muscle state will switch from open to close once rms crosses the threshold
 }

 else if(muscle_state == true && active_toggle == true)
 {
    muscle_state = false; //Muscle state changes from close to open
 }

}


/*
//Actuating the motor according to the intent
void motor_drive() 
{

     uint32_t duty = 900;   // Speed (0–1023)

    if (muscle_state == true && muscle_active == true)
    {
        // CLOSE (forward)
        gpio_set_level(thumb_f, 1);
        gpio_set_level(thumb_b, 0);
        ledc_set_duty(LEDC_MODE, thumb_en_channel, duty);
    }
    else if (muscle_state == false && muscle_active == true)
    {
        // OPEN (reverse)
        gpio_set_level(thumb_f, 0);
        gpio_set_level(thumb_b, 1);
        ledc_set_duty(LEDC_MODE, thumb_en_channel, duty);
    }
    else
    {
        // STOP (important!)
        gpio_set_level(thumb_f, 0);
        gpio_set_level(thumb_b, 0);
        ledc_set_duty(LEDC_MODE, thumb_en_channel, 0);
    }

    ledc_update_duty(LEDC_MODE, thumb_en_channel);

}
    */
   

 
/*
uint32_t angle_to_duty_cycle(uint8_t angle)
{
    if (angle > 180)
        angle = 180;

    return MG90S_MIN_DUTY + 
           ((MG90S_MAX_DUTY - MG90S_MIN_DUTY) * angle) / 180;
}
 */

//Configuring the ADC channel through which data will be received

TaskHandle_t ADCTaskHandle = NULL;
//Declares a FreeRTOS task variable. You later use it when creating the task; can be used to control or delete the task externally.

void ADCTask(void *arg){
//ADC task is the function that will run as a free Rtos task


//Creating the ADC unit
adc_oneshot_unit_handle_t handle= NULL;
adc_oneshot_unit_init_cfg_t init_config1 =
{
    .unit_id= ADC_UNIT_1, //Configuring the ADC channel 1
    .ulp_mode= ADC_ULP_MODE_DISABLE, //turning off ULP interaction
};

   ESP_ERROR_CHECK(adc_oneshot_new_unit(&init_config1, &handle));//For error checking
   //the adc_oneshot_new_unit leads to esp idf creating the adc unit object inside the memory, configuring it to init_config1 and stores the pointer to that object in handle variable
   
    adc_oneshot_chan_cfg_t config = {
    .bitwidth = ADC_BITWIDTH_12, // or you can use ADC_BITWIDTH_DEFAULT here
    .atten = ADC_ATTEN_DB_11, //to map attenuation to 3.3 V, according to the sensor
    };

    ESP_ERROR_CHECK(adc_oneshot_config_channel(handle, ADC_CHANNEL_9, &config)); //Configures the adc channel 9 with the configuartion made
    // You can apply the same config to a different channel or pin 
    // ESP_ERROR_CHECK(adc_oneshot_config_channel(handle, ADC_CHANNEL_8, &config));
    
    //Calibration
    //This is needed to correct the values received by the esp32 becuase some errors exist in the 
    //Not really needed when we are working with the sensor readings ig

    adc_cali_handle_t cali_handle = NULL;

    adc_cali_line_fitting_config_t cali_config = {
        .unit_id = ADC_UNIT_1,
        .atten = ADC_ATTEN_DB_11,        .bitwidth = ADC_BITWIDTH_12,
    };

    ESP_ERROR_CHECK(adc_cali_create_scheme_line_fitting(&cali_config, &cali_handle));
    
    
    for(int i=0;i<N;i++)
    {
        hold_array[i]=0;
    }


    // READ RAW ADC INPUT AND CONVERT TO MILIVOLTS
    while(1)
    {
        ESP_ERROR_CHECK(adc_oneshot_read(handle, ADC_CHANNEL_9, &emg_read));
        printf(" ADC_CHANNEL_9 (GPIO 26) ADC input from signal:   %d \n", emg_read);
        adc_cali_raw_to_voltage(cali_handle, emg_read, &emg_output);
        printf(" Milivolt output after calibration - Channel 9 %d \n", emg_output);
        printf("\n * \n\n");

        update_rms(emg_output);
        
        thresh_update();

        update_muscle_active();

        toggle_detect();

        update_muscle_state();

        
        vTaskDelay(pdMS_TO_TICKS(1)); //This should define the sampling frequency I believe
        //Try to see the delays caused by the other tasks as well. The sampling task should be happening continuously without any interruptions, otherwise aliasing prolly
    }
    adc_oneshot_del_unit(handle);
    adc_cali_delete_scheme_line_fitting(cali_handle);
    vTaskDelete(NULL);
}

void app_main(void)
{

    //Configuring the Motor direction pins
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << thumb_f) | (1ULL << thumb_b),  
        .mode = GPIO_MODE_OUTPUT,              // pins set as output
        .pull_up_en = GPIO_PULLUP_DISABLE,     // Pull-ups disabled
        .pull_down_en = GPIO_PULLDOWN_DISABLE, // Pull-down disabled
        .intr_type = GPIO_INTR_DISABLE         // Interrupts disables
    };
    gpio_config(&io_conf);

    //Configuring the motor pwm pins

    //Configuring the LEDC timer
    ledc_timer_config_t ledc_timer=
    {
        .speed_mode = LEDC_MODE,
        .duty_resolution = LEDC_DUTY_RES,
        .timer_num = LEDC_TIMER,
        .freq_hz= LEDC_FREQUENCY,
    };
    ledc_timer_config(&ledc_timer); //Applies the timer settings to the hardware

    //Configuring the LEDC channel
    //Thumb motor
    ledc_channel_config_t ledc_channel_thumb=
    {
        .gpio_num = thumb_en, //which GPIO pin will the PWM occur in
        .speed_mode = LEDC_MODE, //speed mode
        .channel = thumb_en_channel, //which channel outputs pwm
        .timer_sel = LEDC_TIMER, //which timer it uses
        .duty = 0 
    };
    ledc_channel_config(&ledc_channel_thumb); //Applies the channel settings to the hardware

    /*
    //Index motor
    ledc_channel_config_t ledc_channel_index=
    {
        .gpio_num = index_en, //which GPIO pin will the PWM occur in
        .speed_mode = LEDC_MODE, //speed mode
        .channel = index_en_channel, //which channel outputs pwm
        .timer_sel = LEDC_TIMER, //which timer it uses
        .duty = 0 
    };
    ledc_channel_config(&ledc_channel_index); //Applies the channel settings to the hardware

    //Middle motor
    ledc_channel_config_t ledc_channel_middle=
    {
        .gpio_num = middle_en, //which GPIO pin will the PWM occur in
        .speed_mode = LEDC_MODE, //speed mode
        .channel = middle_en_channel, //which channel outputs pwm
        .timer_sel = LEDC_TIMER, //which timer it uses
        .duty = 0 
    };
    ledc_channel_config(&ledc_channel_middle); //Applies the channel settings to the hardware

    //Ring motor
    ledc_channel_config_t ledc_channel_ring=
    {
        .gpio_num = ring_en, //which GPIO pin will the PWM occur in
        .speed_mode = LEDC_MODE, //speed mode
        .channel = ring_en_channel, //which channel outputs pwm
        .timer_sel = LEDC_TIMER, //which timer it uses
        .duty = 0 
    };
    ledc_channel_config(&ledc_channel_ring); //Applies the channel settings to the hardware

    //Pinky motor
    ledc_channel_config_t ledc_channel_pinky=
    {
        .gpio_num = pinky_en, //which GPIO pin will the PWM occur in
        .speed_mode = LEDC_MODE, //speed mode
        .channel = pinky_en_channel, //which channel outputs pwm
        .timer_sel = LEDC_TIMER, //which timer it uses
        .duty = 0 
    };
    ledc_channel_config(&ledc_channel_pinky); //Applies the channel settings to the hardware
    */


    xTaskCreatePinnedToCore(ADCTask, "ADC Task", 4096, NULL, 10, &ADCTaskHandle, 0); //these values can also be changed for
}


 
